"""Channel ID → display name resolver with in-memory cache."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Module-level cache: channel_id → channel_name
_channel_name_cache: dict[str, str] = {}


async def resolve_channel_name(channel_id: str) -> str:
    """Resolve a channel ID to its display name.

    Uses an in-memory cache to avoid repeated MongoDB lookups.
    Falls back to the raw channel_id if resolution fails.
    """
    if channel_id in _channel_name_cache:
        return _channel_name_cache[channel_id]

    try:
        from beever_atlas.stores import get_stores

        store = get_stores().mongodb
        # Use the existing get_channel_display_name method which queries
        # activity_events for details.channel_name (the canonical source).
        name = await store.get_channel_display_name(channel_id)
        resolved = name if name else channel_id
        _channel_name_cache[channel_id] = resolved
        return resolved
    except Exception:
        logger.debug("Could not resolve channel name for %s", channel_id)
        _channel_name_cache[channel_id] = channel_id
        return channel_id
