"""End-to-end tests for `require_user_loader` signed-token verification (issue #89).

These tests cover the dual-credential flow on the loader dep:
  1. Signed `?loader_token=` is preferred and short-circuits before any other path.
  2. `Authorization: Bearer <key>` header still works (unchanged).
  3. Raw `?access_token=<key>` is accepted ONLY while
     `BEEVER_LOADER_RAW_KEY_FALLBACK=true` (the migration default).
  4. With fallback off, raw `?access_token=` returns 401.
  5. Invalid signed token + valid raw key + fallback on → 200 (fallback path).
  6. Invalid signed token + valid raw key + fallback off → 401.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from beever_atlas.infra import auth as auth_mod
from beever_atlas.infra.auth import (
    Principal,
    require_user_loader,
    require_user_loader_optional,
)
from beever_atlas.infra.config import Settings
from beever_atlas.infra.loader_token import mint_loader_token

_USER_KEY = "user-key-aaaaaaaa"
_SECRET = "loader-secret-32-bytes-of-entropy"


def _patch_settings(monkeypatch, **overrides):
    base = dict(
        api_keys=_USER_KEY,
        bridge_api_key="bridge-secret-xxxxxxxx",
        admin_token="admin-token-xyz",
        loader_token_secret=_SECRET,
        loader_token_ttl=300,
        loader_raw_key_fallback=True,
        allow_bridge_as_user=False,
    )
    base.update(overrides)

    def fake() -> Settings:
        return Settings(**base)  # type: ignore[arg-type]

    monkeypatch.setattr(auth_mod, "get_settings", fake)


def _build_loader_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/files/proxy", dependencies=[Depends(require_user_loader)])
    def files_proxy():
        return {"ok": True}

    @app.get("/api/media/proxy", dependencies=[Depends(require_user_loader)])
    def media_proxy():
        return {"ok": True}

    @app.get("/loader-principal")
    def loader_principal(p: Principal = Depends(require_user_loader)):
        return {"kind": p.kind, "id": p.id}

    return app


def _build_loader_optional_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/ask/shared/{token}")
    def shared(
        token: str,
        p: Optional[Principal] = Depends(require_user_loader_optional),
    ):
        return {"principal": None if p is None else {"kind": p.kind, "id": p.id}}

    return app


def _mint(path: str, ttl: int = 300, secret: str = _SECRET) -> str:
    return mint_loader_token(
        user_id=f"user:{_USER_KEY[:8]}",
        path_prefix=path,
        ttl_seconds=ttl,
        secret=secret,
    )


# ── Signed token path ───────────────────────────────────────────────────


def test_signed_loader_token_accepted(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    client = TestClient(_build_loader_app())
    token = _mint("/api/files/proxy")
    r = client.get(f"/api/files/proxy?loader_token={token}")
    assert r.status_code == 200


def test_signed_token_for_wrong_path_rejected(monkeypatch) -> None:
    """Token bound to /api/files/proxy must NOT verify on /api/media/proxy."""
    _patch_settings(monkeypatch, loader_raw_key_fallback=False)
    client = TestClient(_build_loader_app())
    token = _mint("/api/files/proxy")
    r = client.get(f"/api/media/proxy?loader_token={token}")
    assert r.status_code == 401


def test_signed_token_with_wrong_secret_rejected(monkeypatch) -> None:
    """A token minted with one secret cannot verify under a different secret."""
    _patch_settings(monkeypatch, loader_raw_key_fallback=False)
    client = TestClient(_build_loader_app())
    token = _mint("/api/files/proxy", secret="other-secret")
    r = client.get(f"/api/files/proxy?loader_token={token}")
    assert r.status_code == 401


def test_signed_token_short_circuits_before_raw_key(monkeypatch) -> None:
    """If a valid signed token is present, no raw-key fallback log fires."""
    _patch_settings(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        auth_mod.logger, "info", lambda msg, *a, **kw: calls.append(msg % a if a else msg)
    )
    client = TestClient(_build_loader_app())
    token = _mint("/api/files/proxy")
    r = client.get(
        f"/api/files/proxy?loader_token={token}&access_token={_USER_KEY}",
    )
    assert r.status_code == 200
    assert any("auth.loader_token_verified" in c for c in calls)
    assert not any("auth.loader_fallback_raw_key" in c for c in calls), (
        f"raw-key fallback log must not fire when signed token verifies; got {calls}"
    )


# ── Header path (unchanged behavior) ────────────────────────────────────


def test_header_auth_works_on_loader_router(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    client = TestClient(_build_loader_app())
    r = client.get(
        "/api/files/proxy",
        headers={"Authorization": f"Bearer {_USER_KEY}"},
    )
    assert r.status_code == 200


# ── Raw-key fallback (gated by BEEVER_LOADER_RAW_KEY_FALLBACK) ─────────


def test_raw_key_accepted_when_fallback_on(monkeypatch) -> None:
    _patch_settings(monkeypatch, loader_raw_key_fallback=True)
    calls: list[str] = []
    monkeypatch.setattr(
        auth_mod.logger, "info", lambda msg, *a, **kw: calls.append(msg % a if a else msg)
    )
    client = TestClient(_build_loader_app())
    r = client.get(f"/api/files/proxy?access_token={_USER_KEY}")
    assert r.status_code == 200
    assert any("auth.loader_fallback_raw_key" in c for c in calls), (
        f"raw-key fallback log expected; got {calls}"
    )


def test_raw_key_rejected_when_fallback_off(monkeypatch) -> None:
    _patch_settings(monkeypatch, loader_raw_key_fallback=False)
    client = TestClient(_build_loader_app())
    r = client.get(f"/api/files/proxy?access_token={_USER_KEY}")
    assert r.status_code == 401


def test_invalid_signed_token_falls_back_to_raw_when_flag_on(monkeypatch) -> None:
    """With fallback on, a bad signed token + valid raw key still authenticates."""
    _patch_settings(monkeypatch, loader_raw_key_fallback=True)
    client = TestClient(_build_loader_app())
    r = client.get(
        f"/api/files/proxy?loader_token=bad.token&access_token={_USER_KEY}",
    )
    assert r.status_code == 200


def test_invalid_signed_token_does_not_fall_back_when_flag_off(monkeypatch) -> None:
    """With fallback off, a bad signed token + valid raw key returns 401."""
    _patch_settings(monkeypatch, loader_raw_key_fallback=False)
    client = TestClient(_build_loader_app())
    r = client.get(
        f"/api/files/proxy?loader_token=bad.token&access_token={_USER_KEY}",
    )
    assert r.status_code == 401


def test_no_credential_at_all_rejects(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    client = TestClient(_build_loader_app())
    r = client.get("/api/files/proxy")
    assert r.status_code == 401


# ── Optional dep ────────────────────────────────────────────────────────


def test_loader_optional_accepts_signed_token(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    client = TestClient(_build_loader_optional_app())
    token = _mint("/api/ask/shared/")
    r = client.get(f"/api/ask/shared/abc?loader_token={token}")
    assert r.status_code == 200
    assert r.json()["principal"] is not None


def test_loader_optional_returns_none_on_missing_creds(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    client = TestClient(_build_loader_optional_app())
    r = client.get("/api/ask/shared/abc")
    assert r.status_code == 200
    assert r.json() == {"principal": None}


def test_loader_optional_falls_back_to_raw_key(monkeypatch) -> None:
    _patch_settings(monkeypatch, loader_raw_key_fallback=True)
    client = TestClient(_build_loader_optional_app())
    r = client.get(f"/api/ask/shared/abc?access_token={_USER_KEY}")
    assert r.status_code == 200
    assert r.json()["principal"] is not None
