"""FastMCP server exposing Beever Atlas knowledge tools to MCP clients.

Mounted under /mcp on the main FastAPI app. Auth inherits from FastAPI
middleware — unauthenticated requests are rejected before reaching these tools.
"""

from __future__ import annotations

import logging

import fastmcp

logger = logging.getLogger(__name__)

mcp = fastmcp.FastMCP(
    name="beever-atlas",
    instructions=(
        "Beever Atlas knowledge API. Search channel facts, retrieve wiki pages, "
        "and find domain experts from team communication history."
    ),
)


@mcp.tool()
async def search_channel_knowledge(
    channel_id: str,
    query: str,
    include_graph: bool = False,
) -> dict:
    """Search the channel knowledge base using BM25 + vector hybrid retrieval.

    Args:
        channel_id: The channel to search.
        query: Natural language search query.
        include_graph: If True, also traverses the knowledge graph for entity
            relationships (slower but richer results).

    Returns:
        Dict with 'facts' list and optional 'relationships' list.
    """
    from beever_atlas.agents.tools.memory_tools import search_channel_facts
    from beever_atlas.agents.tools.graph_tools import search_relationships

    facts = await search_channel_facts(channel_id=channel_id, query=query)

    result: dict = {"facts": facts if isinstance(facts, list) else []}

    if include_graph:
        # Extract entity keywords from query for graph traversal
        words = [w for w in query.split() if len(w) > 3]
        entities = words[:3]  # limit to avoid over-querying
        if entities:
            relationships = await search_relationships(
                channel_id=channel_id, entities=entities
            )
            result["relationships"] = (
                relationships if isinstance(relationships, list) else []
            )

    return result


@mcp.tool()
async def get_wiki_page(
    channel_id: str,
    page_type: str = "overview",
) -> dict:
    """Retrieve a compiled wiki page from the MongoDB wiki cache.

    Args:
        channel_id: The channel whose wiki to retrieve.
        page_type: Page type — one of: overview, faq, decisions, people,
            glossary, activity, topics.

    Returns:
        Dict with 'content' (markdown string) and 'generated_at' timestamp,
        or an error message if the page is not cached.
    """
    from beever_atlas.agents.tools.wiki_tools import get_wiki_page as _get_wiki_page

    result = await _get_wiki_page(channel_id=channel_id, page_type=page_type)
    if isinstance(result, dict):
        return result
    return {"content": str(result), "generated_at": None}


@mcp.tool()
async def find_experts(
    channel_id: str,
    topic: str,
) -> dict:
    """Find team members with the most expertise on a given topic.

    Uses Neo4j Person node rankings based on fact count and decision involvement.

    Args:
        channel_id: Channel scope for the expertise search.
        topic: Topic or keyword to rank experts against.

    Returns:
        Dict with 'experts' list — each entry has 'name', 'score', 'evidence'.
    """
    from beever_atlas.agents.tools.graph_tools import find_experts as _find_experts

    result = await _find_experts(channel_id=channel_id, topic=topic)
    if isinstance(result, list):
        return {"experts": result}
    return {"experts": [], "raw": str(result)}
