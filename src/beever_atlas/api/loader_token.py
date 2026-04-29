"""Authenticated endpoint that mints HMAC-signed loader tokens.

Issue #89 — `POST /api/auth/loader-token` accepts `{path: <route-prefix>}`
and returns `{token, expires_at}`. The minted token is bound to the
route prefix and expires after `loader_token_ttl` seconds (default 300).

Auth: `require_user` (header-only — minting itself MUST not be done via
query-string credentials, otherwise we'd have a chicken-and-egg loop).
Rate limit: 100/min per IP via the existing slowapi `limiter` to bound
mint volume in case a buggy client loops.

The path is validated against an explicit allow-list — we do NOT mint
tokens for arbitrary paths, which would turn this endpoint into a
credential-vending oracle for the entire route surface. Today the
allow-list contains exactly the 2 browser-loader routes; future
additions are deliberate code changes, not data-driven.
"""

from __future__ import annotations

import logging
import time
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded  # noqa: F401 (re-export shape)

from beever_atlas.infra.auth import Principal, require_user
from beever_atlas.infra.config import get_settings
from beever_atlas.infra.loader_token import mint_loader_token
from beever_atlas.infra.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Allow-list of route prefixes for which signed loader tokens may be
# minted. Adding a new entry here is a deliberate code change — do NOT
# replace this with a data-driven check (e.g. "any registered route") or
# the mint endpoint becomes a credential oracle for the entire app.
_ALLOWED_LOADER_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/api/files/proxy",
        "/api/media/proxy",
    }
)


class LoaderTokenRequest(BaseModel):
    path: str = Field(
        ...,
        description="Route path to bind the token to (must be on the allow-list).",
        min_length=1,
        max_length=256,
    )


class LoaderTokenResponse(BaseModel):
    token: str = Field(..., description="HMAC-signed loader token (b64payload.b64sig).")
    expires_at: int = Field(..., description="Unix epoch seconds at which the token expires.")


@router.post("/api/auth/loader-token", response_model=LoaderTokenResponse)
@limiter.limit("100/minute")
async def mint_endpoint(
    request: Request,
    body: LoaderTokenRequest,
    principal: Principal = Depends(require_user),
) -> LoaderTokenResponse:
    """Mint a route-scoped, signed loader token for the calling user."""
    if body.path not in _ALLOWED_LOADER_PATHS:
        # 422 (not 404) so a client probing the endpoint can distinguish
        # "your path is invalid" from "the endpoint doesn't exist".
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Path '{body.path}' is not eligible for loader tokens",
        )

    settings = get_settings()
    secret = (settings.loader_token_secret or "").strip()
    if not secret:
        # Configuration error — `_validate_production` warned the operator
        # at boot. We surface a 503 here rather than 500 so monitoring
        # distinguishes "feature unavailable" from "code crashed".
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Loader-token issuance is not configured on this deployment",
        )

    ttl = int(settings.loader_token_ttl)
    token = mint_loader_token(
        user_id=principal.id,
        path_prefix=body.path,
        ttl_seconds=ttl,
        secret=secret,
    )
    return LoaderTokenResponse(token=token, expires_at=int(time.time()) + ttl)
