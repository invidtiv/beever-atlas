"""HMAC-signed scoped tokens for browser-loader URLs.

Issue #89 — replaces the raw user API key on `?access_token=<key>` with
short-lived (5 min default), route-prefix-bound, HMAC-SHA256-signed
tokens carried as `?loader_token=<token>`. Even if a loader URL leaks
to logs/history/screenshots, the credential expires in minutes and is
bound to a specific route prefix.

Token format: ``b64payload.b64signature`` where:
  * ``b64payload`` = base64url-no-padding(JSON({sub, path, exp}))
  * ``b64signature`` = base64url-no-padding(HMAC-SHA256(secret, b64payload))

Stdlib only — no `pyjwt` dependency. The custom 2-part format keeps the
crypto primitive minimal (~30 LOC). The caller (``require_user_loader``)
owns the multi-secret rotation loop so this module's API does not need
to change at rotation time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Final, Optional

logger = logging.getLogger(__name__)

# Tolerate up to 5s of clock skew between mint host and verify host so
# minor NTP drift doesn't reject otherwise-valid tokens at the boundary.
CLOCK_SKEW_GRACE_SECONDS: Final[int] = 5

# Default TTL: 5 minutes. Configurable per-mint via `ttl_seconds=`.
DEFAULT_TTL_SECONDS: Final[int] = 300


def _b64url_encode(data: bytes) -> str:
    """base64url, no padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """base64url decode tolerant of missing padding."""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def mint_loader_token(
    *,
    user_id: str,
    path_prefix: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    secret: str,
) -> str:
    """Mint a signed loader token bound to ``path_prefix`` with ``ttl_seconds``.

    ``user_id`` is recorded as the ``sub`` claim and returned by
    ``verify_loader_token`` on a successful match. ``path_prefix`` MUST be
    a route path (e.g. ``/api/files/proxy``) — query strings are stripped
    by the verifier, which uses ``str.startswith`` against the request's
    ``request.url.path``.

    The token format is ``b64payload.b64signature``. ``secret`` is encoded
    UTF-8 and used as the HMAC-SHA256 key; the input is the b64payload's
    bytes (so the signature is over the canonical encoded form, not the
    raw JSON).
    """
    if not secret:
        raise ValueError("mint_loader_token requires non-empty secret")

    payload = {
        "sub": user_id,
        "path": path_prefix,
        "exp": int(time.time()) + int(ttl_seconds),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_payload = _b64url_encode(payload_bytes)
    sig = hmac.new(
        secret.encode("utf-8"),
        b64_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{b64_payload}.{_b64url_encode(sig)}"


def verify_loader_token(
    token: str,
    *,
    current_path: str,
    secret: str,
) -> Optional[str]:
    """Verify ``token`` against ``secret`` and ``current_path``.

    Returns the embedded ``user_id`` (``sub`` claim) on success. Returns
    ``None`` on ANY failure — bad shape, signature mismatch, decode/parse
    error, expired (beyond ``CLOCK_SKEW_GRACE_SECONDS`` past ``exp``), or
    path-prefix mismatch. Fail-closed.

    Multi-secret key rotation is intentionally NOT handled here. When the
    time comes for a rotation, the caller (``require_user_loader``) will
    try the new secret first then the old secret. Keeping the rotation
    loop in the caller avoids a breaking-signature change to this
    function and keeps each call constant-time per attempt.
    """
    if not token or not secret:
        return None

    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64_payload, b64_sig = parts

        # Recompute signature and compare in constant time.
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            b64_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        provided_sig = _b64url_decode(b64_sig)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        # Decode + parse payload.
        payload_bytes = _b64url_decode(b64_payload)
        payload = json.loads(payload_bytes)

        # Required claims.
        sub = payload.get("sub")
        path = payload.get("path")
        exp = payload.get("exp")
        if not isinstance(sub, str) or not isinstance(path, str):
            return None
        if not isinstance(exp, (int, float)):
            return None

        # Expiry with skew grace.
        if exp + CLOCK_SKEW_GRACE_SECONDS < time.time():
            return None

        # Route-prefix match against the request's path.
        if not current_path.startswith(path):
            return None

        return sub
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
