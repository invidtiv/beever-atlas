"""Coreference resolution service — resolves pronouns and implicit references.

Uses an LLM (Gemini Flash) to rewrite messages with explicit entity names
before they enter the fact/entity extraction pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from beever_atlas.infra.config import get_settings

logger = logging.getLogger(__name__)

# Patterns that indicate pronouns or implicit references worth resolving
_PRONOUN_PATTERN = re.compile(
    r"\b(it|they|them|their|this|that|these|those|he|she|him|her|his|its"
    r"|the project|the tool|the service|the system|the app|the platform"
    r"|the team|the library|the framework|the database|the api)\b",
    re.IGNORECASE,
)


def has_resolvable_references(messages: list[dict[str, Any]]) -> bool:
    """Check if any messages contain pronouns or implicit references.

    Returns False if no resolution is needed (skip LLM call for cost savings).
    """
    for msg in messages:
        text = msg.get("text") or msg.get("content") or ""
        if _PRONOUN_PATTERN.search(text):
            return True
    return False


async def fetch_channel_history(
    channel_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve recent messages from a channel for coreference context.

    Queries MongoDB for raw messages, falling back gracefully if unavailable.
    """
    try:
        from beever_atlas.stores import get_stores
        stores = get_stores()
        records = await stores.mongodb.db["raw_messages"].find(
            {"channel_id": channel_id},
            sort=[("message_ts", -1)],
            limit=limit,
        ).to_list(length=limit)
        return [
            {
                "author": r.get("author_name") or r.get("author") or "unknown",
                "text": r.get("text") or r.get("content") or "",
                "ts": r.get("message_ts") or r.get("ts") or "",
            }
            for r in reversed(records)
        ]
    except Exception:
        logger.warning(
            "CoreferenceResolver: channel history unavailable for %s",
            channel_id,
            exc_info=True,
        )
        return []


async def resolve_coreferences(
    batch_messages: list[dict[str, Any]],
    history_messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Resolve pronouns and implicit references in batch messages.

    Args:
        batch_messages: Current batch messages to resolve (will be modified).
        history_messages: Recent channel history for cross-batch context.

    Returns:
        The same message dicts with ``text`` replaced by resolved text
        and ``raw_text`` preserving the original.
    """
    if not batch_messages:
        return batch_messages

    # Cost optimization: skip LLM call if no pronouns detected
    if not has_resolvable_references(batch_messages):
        logger.debug("CoreferenceResolver: no pronouns detected, skipping LLM call")
        for msg in batch_messages:
            msg["raw_text"] = msg.get("text") or msg.get("content") or ""
        return batch_messages

    settings = get_settings()

    # Build prompt context
    prompt_parts: list[str] = []
    if history_messages:
        for hm in history_messages:
            prompt_parts.append(
                f"[HISTORY] {hm.get('author', 'unknown')}: {hm.get('text', '')}"
            )

    for i, msg in enumerate(batch_messages):
        author = msg.get("username") or msg.get("user") or msg.get("author") or "unknown"
        text = msg.get("text") or msg.get("content") or ""
        prompt_parts.append(f"[CURRENT BATCH] (index={i}) {author}: {text}")

    messages_text = "\n".join(prompt_parts)

    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=settings.google_api_key)

        from beever_atlas.agents.prompts.coreference_resolver import (
            COREFERENCE_RESOLVER_INSTRUCTION,
        )

        instruction = COREFERENCE_RESOLVER_INSTRUCTION.replace("{messages}", messages_text)

        response = await client.aio.models.generate_content(
            model=settings.coref_model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=instruction)],
                )
            ],
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        result_text = response.text or ""
        # Strip markdown fences if present
        if result_text.startswith("```"):
            result_text = re.sub(r"^```(?:json)?\n?", "", result_text)
            result_text = re.sub(r"\n?```$", "", result_text)

        result = json.loads(result_text)
        resolved = result.get("resolved_messages") or []

        # Apply resolved text back to batch messages
        resolved_by_index = {r["index"]: r["text"] for r in resolved if "index" in r and "text" in r}

        for i, msg in enumerate(batch_messages):
            original_text = msg.get("text") or msg.get("content") or ""
            msg["raw_text"] = original_text
            if i in resolved_by_index:
                msg["text"] = resolved_by_index[i]

        logger.info(
            "CoreferenceResolver: resolved %d/%d messages",
            len(resolved_by_index),
            len(batch_messages),
        )

    except Exception:
        logger.warning(
            "CoreferenceResolver: LLM call failed, preserving original text",
            exc_info=True,
        )
        for msg in batch_messages:
            msg["raw_text"] = msg.get("text") or msg.get("content") or ""

    return batch_messages
