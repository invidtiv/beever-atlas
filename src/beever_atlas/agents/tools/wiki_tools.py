"""Wiki and topic overview tools for the QA agent."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SUPPORTED_PAGE_TYPES = frozenset(
    {"overview", "faq", "decisions", "people", "glossary", "activity", "topics"}
)


async def get_wiki_page(channel_id: str, page_type: str) -> dict | None:
    """Retrieve a pre-compiled wiki page from MongoDB wiki_cache.

    Cost: $0. Target latency: <50ms (cache read only, no Weaviate/Neo4j queries).

    Args:
        channel_id: The channel to look up.
        page_type: One of: overview, faq, decisions, people, glossary, activity, topics.

    Returns:
        Dict with page_type, content (markdown), and summary — or None if unavailable.
    """
    if page_type not in SUPPORTED_PAGE_TYPES:
        return None
    try:
        from beever_atlas.infra.config import get_settings
        from beever_atlas.wiki.cache import WikiCache

        settings = get_settings()
        cache = WikiCache(settings.mongodb_uri)
        page = await cache.get_page(channel_id, page_type)
        if page is None:
            return None
        return {
            "page_type": page_type,
            "content": page.get("content", ""),
            "summary": page.get("summary", ""),
        }
    except Exception:
        logger.exception(
            "get_wiki_page failed for channel=%s page_type=%s", channel_id, page_type
        )
        return None


async def get_topic_overview(
    channel_id: str, topic_name: str | None = None
) -> dict | None:
    """Retrieve channel-level summary (Tier 0) or a topic cluster summary (Tier 1).

    Cost: $0 (cached). Target latency: <50ms.

    Args:
        channel_id: The channel to look up.
        topic_name: Optional topic to narrow to a matching Tier 1 cluster.

    Returns:
        Dict with tier, summary, and metadata — or None if unavailable.
    """
    try:
        from beever_atlas.stores import get_stores

        store = get_stores().weaviate

        if topic_name is None:
            summary = await store.get_channel_summary(channel_id)
            if summary is None:
                return None
            return {
                "tier": "summary",
                "summary": summary.text,
                "cluster_count": summary.cluster_count,
                "fact_count": summary.fact_count,
            }

        clusters = await store.list_clusters(channel_id)
        topic_lower = topic_name.lower()
        best = None
        for cluster in clusters:
            tags = [t.lower() for t in (cluster.topic_tags or [])]
            if any(topic_lower in t or t in topic_lower for t in tags):
                best = cluster
                break
        if best is None and clusters:
            best = clusters[0]
        if best is None:
            return None
        return {
            "tier": "topic",
            "cluster_id": best.id,
            "summary": best.summary,
            "topic_tags": best.topic_tags,
            "member_count": best.member_count,
        }
    except Exception:
        logger.exception(
            "get_topic_overview failed for channel=%s topic=%s", channel_id, topic_name
        )
        return None
