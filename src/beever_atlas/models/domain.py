"""Domain models: core graph and fact entities."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AtomicFact(BaseModel):
    """A single extracted fact stored in Weaviate (Tier 2)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_text: str
    quality_score: float = 0.0
    tier: str = "atomic"
    cluster_id: str | None = None
    channel_id: str = ""
    platform: str = "slack"
    author_id: str = ""
    author_name: str = ""
    message_ts: str = ""
    thread_ts: str | None = None
    source_message_id: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    entity_tags: list[str] = Field(default_factory=list)
    action_tags: list[str] = Field(default_factory=list)
    importance: str = "medium"
    graph_entity_ids: list[str] = Field(default_factory=list)
    source_media_url: str = ""  # Deprecated: use source_media_urls
    source_media_type: str = ""  # "image", "pdf", "doc", "video", ""
    source_media_urls: list[str] = Field(default_factory=list)
    source_media_names: list[str] = Field(default_factory=list)
    source_link_urls: list[str] = Field(default_factory=list)
    source_link_titles: list[str] = Field(default_factory=list)
    source_link_descriptions: list[str] = Field(default_factory=list)
    valid_at: datetime | None = None
    invalid_at: datetime | None = None
    superseded_by: str | None = None
    supersedes: str | None = None
    potential_contradiction: bool = False
    text_vector: list[float] | None = None
    fact_type: str = ""  # "decision", "opinion", "observation", "action_item", "question"
    thread_context_summary: str = ""  # Brief summary of thread deliberation

    @staticmethod
    def deterministic_id(platform: str, channel_id: str, message_ts: str, fact_index: int = 0) -> str:
        """Generate a deterministic UUID for idempotent upserts."""
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        return str(uuid.uuid5(namespace, f"{platform}:{channel_id}:{message_ts}:{fact_index}"))


class GraphEntity(BaseModel):
    """An entity node in the Neo4j knowledge graph."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str  # Person, Decision, Project, Technology, etc.
    scope: str = "global"  # "global" or "channel"
    channel_id: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    status: str = "active"  # "active" or "pending"
    pending_since: datetime | None = None
    name_vector: list[float] | None = None
    source_fact_ids: list[str] = Field(default_factory=list)
    source_message_id: str = ""
    message_ts: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class GraphRelationship(BaseModel):
    """A relationship edge in the Neo4j knowledge graph."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # DECIDED, WORKS_ON, USES, etc.
    source: str  # Source entity name
    target: str  # Target entity name
    confidence: float = 0.0
    valid_from: str | None = None
    valid_until: str | None = None
    context: str = ""
    source_message_id: str = ""
    source_fact_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class Subgraph(BaseModel):
    """A subgraph returned from Neo4j traversal queries."""

    nodes: list[GraphEntity] = Field(default_factory=list)
    edges: list[GraphRelationship] = Field(default_factory=list)


class TopicCluster(BaseModel):
    """A Tier 1 topic cluster grouping related atomic facts."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tier: str = "topic"
    channel_id: str
    summary: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    member_ids: list[str] = Field(default_factory=list)
    member_count: int = 0
    centroid_vector: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    # Enrichment fields (R4)
    key_entities: list[dict[str, str]] = Field(default_factory=list)  # [{"id", "name", "type"}]
    key_relationships: list[dict[str, str]] = Field(default_factory=list)  # [{"source", "type", "target", "confidence"}]
    date_range_start: str = ""
    date_range_end: str = ""
    authors: list[str] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list)
    media_names: list[str] = Field(default_factory=list)
    link_refs: list[str] = Field(default_factory=list)
    high_importance_count: int = 0
    related_cluster_ids: list[str] = Field(default_factory=list)
    staleness_score: float = 0.0  # 0.0=fresh, 1.0=very stale
    status: str = "active"  # "active", "completed", "stale"
    fact_type_counts: dict[str, int] = Field(default_factory=dict)  # {"decision": N, ...}


class ChannelSummary(BaseModel):
    """A Tier 0 channel-level summary consolidating all topic clusters."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tier: str = "summary"
    channel_id: str
    text: str = ""
    cluster_count: int = 0
    fact_count: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    # Enrichment fields (R4)
    key_decisions: list[dict[str, str]] = Field(default_factory=list)
    key_entities: list[dict[str, str]] = Field(default_factory=list)
    key_topics: list[dict[str, Any]] = Field(default_factory=list)
    date_range_start: str = ""
    date_range_end: str = ""
    media_count: int = 0
    author_count: int = 0
    worst_staleness: float = 0.0


class EntityKnowledgeCard(BaseModel):
    """Cross-channel aggregation of all knowledge about a single graph entity."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tier: str = "entity_card"
    entity_id: str = ""
    entity_name: str = ""
    entity_type: str = ""
    channel_ids: list[str] = Field(default_factory=list)
    cluster_ids: list[str] = Field(default_factory=list)
    fact_count: int = 0
    fact_type_breakdown: dict[str, int] = Field(default_factory=dict)
    key_facts: list[str] = Field(default_factory=list)
    related_entities: list[dict[str, str]] = Field(default_factory=list)
    last_mentioned_at: str = ""
    staleness_score: float = 0.0
    summary: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
