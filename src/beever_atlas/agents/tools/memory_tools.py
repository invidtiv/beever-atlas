"""Memory retrieval tools: QA history, channel facts, media references, activity."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from beever_atlas.agents.tools.channel_resolver import resolve_channel_name

logger = logging.getLogger(__name__)


def _format_timestamp(ts: str | None) -> str:
    """Convert Slack epoch timestamp to ISO date string."""
    if not ts:
        return "(unavailable)"
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "(unavailable)"


async def search_qa_history(channel_id: str, query: str, limit: int = 5) -> list[dict]:
    """Search past Q&A pairs semantically for similar questions in this channel.

    Cost: $0. Target latency: <100ms.

    Args:
        channel_id: Scope search to this channel.
        query: Search query.
        limit: Max results.

    Returns:
        List of past Q&A entries with question, answer, citations, timestamp.
    """
    try:
        from beever_atlas.infra.config import get_settings
        from beever_atlas.stores.qa_history_store import QAHistoryStore

        settings = get_settings()
        store = QAHistoryStore(settings.weaviate_url, settings.weaviate_api_key)
        await store.startup()
        results = await store.search_qa_history(channel_id=channel_id, query=query, limit=limit)
        await store.shutdown()
        return results
    except Exception:
        logger.exception("search_qa_history failed for channel=%s query=%s", channel_id, query)
        return []


async def search_channel_facts(
    channel_id: str,
    query: str,
    time_scope: str = "any",
    limit: int = 10,
) -> list[dict]:
    """BM25 keyword search over atomic facts (Weaviate Tier 2 / tier=atomic).

    Cost: ~$0.001. Target latency: <200ms.

    Args:
        channel_id: Scope to this channel.
        query: Search query.
        time_scope: "recent" (last 30 days) or "any".
        limit: Max results.

    Returns:
        Ranked facts with author, channel, timestamp, permalink, confidence.
    """
    try:
        from beever_atlas.stores import get_stores

        store = get_stores().weaviate
        facts = await store.bm25_search(
            query=query, channel_id=channel_id, tier="atomic", limit=limit * 2
        )

        cutoff: datetime | None = None
        if time_scope == "recent":
            cutoff = datetime.now(tz=UTC) - timedelta(days=30)

        output = []
        for fact in facts:
            if cutoff and fact.message_ts:
                try:
                    ts = float(fact.message_ts)
                    fact_dt = datetime.fromtimestamp(ts, tz=UTC)
                    if fact_dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
            output.append({
                "text": fact.memory_text,
                "author": fact.author_name,
                "channel_id": fact.channel_id,
                "channel_name": await resolve_channel_name(fact.channel_id),
                "timestamp": _format_timestamp(fact.message_ts),
                "permalink": fact.source_message_id,
                "importance": fact.importance,
                "confidence": round(fact.quality_score / 10.0, 2) if fact.quality_score else 0.5,
                "fact_id": fact.id,
                "topic_tags": fact.topic_tags,
            })
            if len(output) >= limit:
                break
        return output
    except Exception:
        logger.exception("search_channel_facts failed for channel=%s query=%s", channel_id, query)
        return []


async def search_media_references(
    channel_id: str,
    query: str,
    media_type: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Search for images, PDFs, and links shared in the channel.

    Cost: ~$0.001. Target latency: <200ms.

    Args:
        channel_id: Scope to this channel.
        query: Search query.
        media_type: "image", "pdf", "link", or None for all.
        limit: Max results.

    Returns:
        Media items with URL, type, and surrounding message context.
    """
    try:
        from beever_atlas.stores import get_stores

        store = get_stores().weaviate
        facts = await store.bm25_search(
            query=query, channel_id=channel_id, tier="atomic", limit=limit * 4
        )

        output = []
        for fact in facts:
            has_images = bool(fact.source_media_urls)
            has_links = bool(fact.source_link_urls)
            has_pdfs = any(".pdf" in u for u in (fact.source_link_urls or []))

            if media_type == "image" and not has_images:
                continue
            if media_type == "pdf" and not has_pdfs:
                continue
            if media_type == "link" and not has_links:
                continue
            if media_type is None and not (has_images or has_links):
                continue

            output.append({
                "text": fact.memory_text,
                "media_urls": fact.source_media_urls or [],
                "link_urls": fact.source_link_urls or [],
                "link_titles": fact.source_link_titles or [],
                "author": fact.author_name,
                "channel_name": await resolve_channel_name(fact.channel_id) if fact.channel_id else "",
                "timestamp": _format_timestamp(fact.message_ts),
                "media_type": fact.source_media_type or "unknown",
            })
            if len(output) >= limit:
                break
        return output
    except Exception:
        logger.exception("search_media_references failed for channel=%s", channel_id)
        return []


async def get_recent_activity(
    channel_id: str,
    days: int = 7,
    topic: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return recent facts from the channel, optionally filtered by topic.

    Cost: $0. Target latency: <200ms.

    Args:
        channel_id: Scope to this channel.
        days: How many days back to look.
        topic: Optional topic filter.
        limit: Max results.

    Returns:
        Facts from the last N days ordered by timestamp descending.
    """
    try:
        from beever_atlas.stores import get_stores

        store = get_stores().weaviate
        search_query = topic or "recent updates"
        facts = await store.bm25_search(
            query=search_query, channel_id=channel_id, tier="atomic", limit=limit * 3
        )

        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        output = []
        for fact in facts:
            if fact.message_ts:
                try:
                    ts = float(fact.message_ts)
                    fact_dt = datetime.fromtimestamp(ts, tz=UTC)
                    if fact_dt >= cutoff:
                        output.append({
                            "text": fact.memory_text,
                            "author": fact.author_name,
                            "channel_name": await resolve_channel_name(fact.channel_id) if hasattr(fact, "channel_id") and fact.channel_id else "",
                            "timestamp": _format_timestamp(fact.message_ts),
                            "importance": fact.importance,
                            "topic_tags": fact.topic_tags,
                        })
                except (ValueError, TypeError):
                    pass

        output.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return output[:limit]
    except Exception:
        logger.exception("get_recent_activity failed for channel=%s", channel_id)
        return []
