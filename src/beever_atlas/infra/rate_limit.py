"""Shared IP-keyed rate limiter.

Kept in its own module so the limiter instance can be imported by both
`server/app.py` and route modules (e.g. `api/ask.py`) without causing a
circular import.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from beever_atlas.infra.config import get_settings

_settings = get_settings()
_storage_uri = _settings.redis_url or "memory://"

limiter = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)
