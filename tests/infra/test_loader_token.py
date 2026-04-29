"""Unit tests for the HMAC-signed loader-token primitive (issue #89).

Covers `mint_loader_token` + `verify_loader_token`:
  * round-trip
  * bad signature
  * expired (beyond skew grace)
  * within skew grace (accepted)
  * beyond skew grace (rejected)
  * wrong path
  * path-prefix match
  * malformed input
  * empty secret
  * constant-time signature compare
"""

from __future__ import annotations

import hmac
import time

import pytest

from beever_atlas.infra import loader_token as lt_mod
from beever_atlas.infra.loader_token import (
    CLOCK_SKEW_GRACE_SECONDS,
    mint_loader_token,
    verify_loader_token,
)

_SECRET = "x" * 32  # 32-byte secret matches production guidance
_USER_ID = "user:abc123def456"


def test_mint_roundtrip() -> None:
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    assert verify_loader_token(token, current_path="/api/files/proxy", secret=_SECRET) == _USER_ID


def test_mint_token_is_two_part_dot_separated() -> None:
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    parts = token.split(".")
    assert len(parts) == 2
    assert all(p for p in parts)


def test_verify_bad_signature_returns_none() -> None:
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    payload, sig = token.split(".")
    # Flip one byte of the signature.
    tampered_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    tampered = f"{payload}.{tampered_sig}"
    assert verify_loader_token(tampered, current_path="/api/files/proxy", secret=_SECRET) is None


def test_verify_expired_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token whose `exp` is far past, beyond the skew grace, MUST be rejected."""
    base = int(time.time())
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=10,
        secret=_SECRET,
    )
    # Jump past exp + grace.
    monkeypatch.setattr(
        lt_mod.time,
        "time",
        lambda: base + 10 + CLOCK_SKEW_GRACE_SECONDS + 1,
    )
    assert verify_loader_token(token, current_path="/api/files/proxy", secret=_SECRET) is None


def test_verify_within_skew_window_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token whose `exp` is 3 seconds past should still verify (within 5s grace)."""
    base = int(time.time())
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=10,
        secret=_SECRET,
    )
    # Move clock so we're 3 seconds past `exp` (within grace).
    monkeypatch.setattr(lt_mod.time, "time", lambda: base + 10 + 3)
    assert verify_loader_token(token, current_path="/api/files/proxy", secret=_SECRET) == _USER_ID


def test_verify_beyond_skew_window_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """6 seconds past `exp` (1 beyond grace) MUST be rejected."""
    base = int(time.time())
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=10,
        secret=_SECRET,
    )
    monkeypatch.setattr(lt_mod.time, "time", lambda: base + 10 + 6)
    assert verify_loader_token(token, current_path="/api/files/proxy", secret=_SECRET) is None


def test_verify_wrong_path_returns_none() -> None:
    """Token bound to /api/files/proxy must not verify against /api/media/proxy."""
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    assert verify_loader_token(token, current_path="/api/media/proxy", secret=_SECRET) is None


def test_verify_path_prefix_match_succeeds() -> None:
    """Token bound to a route works for any sub-path of that route — query
    string is stripped by FastAPI's `request.url.path`, so the verify call
    only sees the route portion."""
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files",
        ttl_seconds=300,
        secret=_SECRET,
    )
    assert verify_loader_token(token, current_path="/api/files/proxy", secret=_SECRET) == _USER_ID


def test_verify_malformed_token_returns_none() -> None:
    """Empty, no-dot, three-dots, non-base64, all return None (fail-closed)."""
    for bad in ("", "no-dot", "a.b.c", "@@@.@@@", "!!!"):
        assert verify_loader_token(bad, current_path="/api/files/proxy", secret=_SECRET) is None


def test_verify_empty_secret_returns_none() -> None:
    """Empty verify-secret must return None (not raise)."""
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    assert verify_loader_token(token, current_path="/api/files/proxy", secret="") is None


def test_mint_empty_secret_raises() -> None:
    """Mint with empty secret raises — operator should never produce
    unsigned tokens."""
    with pytest.raises(ValueError):
        mint_loader_token(
            user_id=_USER_ID,
            path_prefix="/api/files/proxy",
            ttl_seconds=300,
            secret="",
        )


def test_constant_time_compare_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify exercises `hmac.compare_digest` (not naive `==`)."""
    calls: list[tuple] = []
    real = hmac.compare_digest

    def tracking_compare(a, b):  # type: ignore[no-untyped-def]
        calls.append((type(a), type(b)))
        return real(a, b)

    monkeypatch.setattr(lt_mod.hmac, "compare_digest", tracking_compare)
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    verify_loader_token(token, current_path="/api/files/proxy", secret=_SECRET)
    assert calls, "verify_loader_token must call hmac.compare_digest at least once"


def test_mint_payload_does_not_leak_secret_in_token() -> None:
    """The signing secret must not appear in the produced token (sanity check)."""
    token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    assert _SECRET not in token


def test_verify_succeeds_after_path_change_with_new_token() -> None:
    """A new mint for a different path-prefix succeeds against that path."""
    files_token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/files/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    media_token = mint_loader_token(
        user_id=_USER_ID,
        path_prefix="/api/media/proxy",
        ttl_seconds=300,
        secret=_SECRET,
    )
    assert (
        verify_loader_token(files_token, current_path="/api/files/proxy", secret=_SECRET)
        == _USER_ID
    )
    assert (
        verify_loader_token(media_token, current_path="/api/media/proxy", secret=_SECRET)
        == _USER_ID
    )
    # Cross-check: each token must NOT verify against the other path.
    assert verify_loader_token(files_token, current_path="/api/media/proxy", secret=_SECRET) is None
    assert verify_loader_token(media_token, current_path="/api/files/proxy", secret=_SECRET) is None
