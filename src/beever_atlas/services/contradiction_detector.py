"""Contradiction detection service for temporal fact lifecycle.

Compares newly extracted facts against existing facts to detect
contradictions and trigger fact supersession.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from beever_atlas.infra.config import get_settings
from beever_atlas.models import AtomicFact

logger = logging.getLogger(__name__)


async def detect_contradictions(
    new_fact: AtomicFact,
    existing_facts: list[AtomicFact],
) -> list[dict[str, Any]]:
    """Compare a new fact against existing facts for contradictions.

    Returns list of dicts with ``existing_fact_id``, ``confidence``, ``reason``.
    """
    if not existing_facts:
        return []

    settings = get_settings()

    # Format existing facts for the prompt
    existing_lines: list[str] = []
    for ef in existing_facts:
        existing_lines.append(
            f"- ID: {ef.id} | Text: {ef.memory_text} | "
            f"Topics: {ef.topic_tags} | Entities: {ef.entity_tags}"
        )

    from beever_atlas.agents.prompts.contradiction_detector import (
        CONTRADICTION_DETECTOR_INSTRUCTION,
    )

    instruction = CONTRADICTION_DETECTOR_INSTRUCTION.replace(
        "{new_fact}",
        f"Text: {new_fact.memory_text} | Topics: {new_fact.topic_tags} | Entities: {new_fact.entity_tags}",
    ).replace("{existing_facts}", "\n".join(existing_lines))

    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=settings.google_api_key)

        response = await client.aio.models.generate_content(
            model=settings.llm_fast_model,
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
        if result_text.startswith("```"):
            result_text = re.sub(r"^```(?:json)?\n?", "", result_text)
            result_text = re.sub(r"\n?```$", "", result_text)

        result = json.loads(result_text)
        return result.get("contradictions") or []

    except Exception:
        logger.warning(
            "ContradictionDetector: LLM call failed",
            exc_info=True,
        )
        return []


async def check_and_supersede(
    new_facts: list[AtomicFact],
    channel_id: str,
) -> None:
    """Check new facts for contradictions against existing facts and apply supersession.

    For each new fact:
    1. Query existing facts with overlapping entity/topic tags
    2. Run contradiction detection
    3. Auto-supersede at confidence >= threshold
    4. Flag potential contradictions at lower confidence
    """
    from beever_atlas.stores import get_stores
    from beever_atlas.models import MemoryFilters

    settings = get_settings()
    stores = get_stores()

    for new_fact in new_facts:
        if not new_fact.entity_tags and not new_fact.topic_tags:
            continue

        # Query existing facts with overlapping tags
        try:
            existing: list[AtomicFact] = []
            if new_fact.entity_tags:
                result = await stores.weaviate.list_facts(
                    channel_id=channel_id,
                    filters=MemoryFilters(entity=new_fact.entity_tags[0]),
                    limit=10,
                )
                existing.extend(result.memories)

            # Deduplicate and exclude self
            seen_ids: set[str] = set()
            candidates: list[AtomicFact] = []
            for ef in existing:
                if ef.id != new_fact.id and ef.id not in seen_ids and ef.invalid_at is None:
                    seen_ids.add(ef.id)
                    candidates.append(ef)

            if not candidates:
                continue

            contradictions = await detect_contradictions(new_fact, candidates[:10])

            for contradiction in contradictions:
                fact_id = contradiction.get("existing_fact_id", "")
                confidence = float(contradiction.get("confidence", 0))

                if confidence >= settings.contradiction_confidence_threshold:
                    # Auto-supersede
                    await stores.weaviate.supersede_fact(
                        old_fact_id=fact_id,
                        new_fact_id=new_fact.id,
                    )
                    logger.info(
                        "ContradictionDetector: superseded fact %s with %s (confidence=%.2f)",
                        fact_id,
                        new_fact.id,
                        confidence,
                    )
                elif confidence >= settings.contradiction_flag_threshold:
                    # Flag as potential contradiction
                    await stores.weaviate.flag_potential_contradiction(new_fact.id)
                    logger.info(
                        "ContradictionDetector: flagged potential contradiction on %s (confidence=%.2f)",
                        new_fact.id,
                        confidence,
                    )

        except Exception:
            logger.warning(
                "ContradictionDetector: check failed for fact %s",
                new_fact.id,
                exc_info=True,
            )
