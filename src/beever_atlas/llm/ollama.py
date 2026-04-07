"""Ollama local model integration — health check and model discovery."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from beever_atlas.infra.config import get_settings

logger = logging.getLogger(__name__)


async def check_ollama_health() -> dict[str, Any]:
    """Ping the Ollama API and return connection status + available models.

    Returns:
        {"connected": bool, "models": list[str]}
    """
    settings = get_settings()
    if not settings.ollama_enabled:
        return {"connected": False, "models": []}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_api_base}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"connected": True, "models": models}
    except Exception:
        logger.debug("Ollama health check failed", exc_info=True)
        return {"connected": False, "models": []}
