"""Knowledge graph API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from beever_atlas.stores import get_stores
from beever_atlas.models import GraphEntity, GraphRelationship, Subgraph

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/entities", response_model=list[GraphEntity])
async def list_entities(
    channel_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[GraphEntity]:
    """List entities in the knowledge graph."""
    stores = get_stores()
    return await stores.neo4j.list_entities(channel_id=channel_id, entity_type=entity_type, limit=limit)


@router.get("/relationships", response_model=list[GraphRelationship])
async def list_relationships(
    channel_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[GraphRelationship]:
    """List relationships in the knowledge graph, including entity-media links."""
    stores = get_stores()
    entity_rels = await stores.neo4j.list_relationships(channel_id=channel_id, limit=limit)

    # Also fetch entity→media relationships and convert to GraphRelationship
    media_rels_raw = await stores.neo4j.list_media_relationships(channel_id=channel_id, limit=100)
    for mr in media_rels_raw:
        entity_rels.append(GraphRelationship(
            type=mr["type"],
            source=mr["source"],
            target=mr["target"],
        ))

    return entity_rels


@router.get("/entities/{entity_id}/neighbors", response_model=Subgraph)
async def get_entity_neighbors(
    entity_id: str,
    hops: int = Query(default=1, ge=1, le=5),
    limit: int = Query(default=50, ge=1, le=500),
) -> Subgraph:
    """Get the N-hop neighborhood subgraph for an entity."""
    stores = get_stores()
    return await stores.neo4j.get_neighbors(entity_id, hops=hops, limit=limit)


@router.get("/media", response_model=list[dict])
async def list_media(
    channel_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    """List media nodes in the knowledge graph."""
    stores = get_stores()
    return await stores.neo4j.list_media(channel_id=channel_id, limit=limit)


@router.get("/decisions/{channel_id}", response_model=list[GraphEntity])
async def get_decisions(
    channel_id: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> list[GraphEntity]:
    """Get the decision timeline for a channel."""
    stores = get_stores()
    return await stores.neo4j.get_decisions(channel_id, limit=limit)
