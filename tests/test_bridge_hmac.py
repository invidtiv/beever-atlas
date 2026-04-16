"""Tests for the bridge bearer-token contract.

Previously this file validated the inline HMAC check inside
`list_connections_with_credentials`. After commit `5505c44` (H4) that
check was lifted into the reusable `require_bridge` dependency and the
`/api/internal/connections/credentials` route moved onto a dedicated
internal router guarded by it. The tests here now pin the same contract
against `require_bridge` directly.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from beever_atlas.infra import auth as auth_mod
from beever_atlas.infra.auth import require_bridge
from beever_atlas.infra.config import Settings


def _patch_settings(monkeypatch, **overrides):
    base: dict = dict(
        api_keys="user-key",
        bridge_api_key="s3cret",
        admin_token="admin-tok",
    )
    base.update(overrides)

    def fake_get_settings() -> Settings:
        return Settings(**base)  # type: ignore[arg-type]

    monkeypatch.setattr(auth_mod, "get_settings", fake_get_settings)


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/internal", dependencies=[Depends(require_bridge)])
    def internal_route():
        return {"ok": True}

    return app


def test_bridge_auth_accepts_valid_bearer(monkeypatch):
    _patch_settings(monkeypatch)
    client = TestClient(_build_app())
    r = client.get("/internal", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200


def test_bridge_auth_rejects_wrong_key(monkeypatch):
    _patch_settings(monkeypatch)
    client = TestClient(_build_app())
    r = client.get("/internal", headers={"Authorization": "Bearer WRONG"})
    assert r.status_code == 401


def test_bridge_auth_rejects_missing_header(monkeypatch):
    _patch_settings(monkeypatch)
    client = TestClient(_build_app())
    assert client.get("/internal").status_code == 401


def test_bridge_auth_rejects_user_key(monkeypatch):
    """A user API key must never satisfy the bridge dependency."""
    _patch_settings(monkeypatch)
    client = TestClient(_build_app())
    r = client.get("/internal", headers={"Authorization": "Bearer user-key"})
    assert r.status_code == 401


def test_bridge_auth_uses_compare_digest(monkeypatch):
    """The bridge path uses hmac.compare_digest (timing-safe)."""
    calls = {"n": 0}
    original = hmac.compare_digest

    def _spy(a, b):
        calls["n"] += 1
        return original(a, b)

    monkeypatch.setattr(auth_mod.hmac, "compare_digest", _spy)
    _patch_settings(monkeypatch)
    client = TestClient(_build_app())
    r = client.get("/internal", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200
    assert calls["n"] >= 1


def test_bridge_auth_401_when_key_unconfigured(monkeypatch):
    """When BRIDGE_API_KEY is empty, every request is rejected —
    there is no configured key to match, so the dependency cannot
    succeed."""
    _patch_settings(monkeypatch, bridge_api_key="")
    client = TestClient(_build_app())
    r = client.get("/internal", headers={"Authorization": "Bearer whatever"})
    assert r.status_code == 401
