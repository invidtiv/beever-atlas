# Beever Atlas v2: Technical Architecture Proposal

> **Date**: 2026-03-24 (v3 — final revision)
> **Status**: Proposal — under review
> **Scope**: Full architecture redesign from demo to production-ready system
> **Deliverable**: Architecture validation document

---

## 1. Executive Summary

Beever Atlas v1 demonstrated that a wiki-first, hierarchical memory system for Slack channels is viable. However, the demo-stage implementation has 15 validated weaknesses: cluster linking is a no-op, the query classifier uses brittle regex, memory quality is 5.25/10, temporal decay is never applied, and there is no support for relational queries.

**Beever Atlas v2** redesigns the system around two complementary memory systems:

- **Semantic Memory (Weaviate)** — Hierarchical 3-tier memory (improved from v1) handling factual, topic-based, and overview queries via hybrid BM25+vector search. Handles ~80% of queries. Cheap, fast.
- **Graph Memory (Neo4j)** — Flexible knowledge graph capturing entity relationships and temporal evolution from conversations. Handles relational queries that semantic search can't answer. ~20% of queries.
- **Smart Router** — LLM-powered query understanding that routes to Semantic, Graph, or both in parallel based on query type and cost optimization.

**Design Principle**: Each memory system does what it's best at. They don't duplicate each other's work. Weaviate owns facts and topics. Neo4j owns entities and relationships. The router decides which to use.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BEEVER ATLAS v2 OVERVIEW                        │
│                                                                         │
│                         ┌──────────────┐                                │
│                         │  Smart Query │                                │
│              ┌──────────│    Router    │──────────┐                     │
│              │          └──────────────┘          │                     │
│              ▼                                    ▼                     │
│  ┌─────────────────────────┐     ┌─────────────────────────┐          │
│  │   SEMANTIC MEMORY       │     │    GRAPH MEMORY         │          │
│  │   (Weaviate)            │     │    (Neo4j)              │          │
│  │                         │     │                         │          │
│  │  Tier 0: Summary        │     │  Flexible entities:     │          │
│  │  Tier 1: Topic Clusters │     │  Person, Decision,      │          │
│  │  Tier 2: Atomic Facts   │     │  Project, Technology,   │          │
│  │                         │     │  Team, Meeting, ...     │          │
│  │  Hybrid BM25+Vector     │     │  Flexible relationships │          │
│  │  Cross-modal (img/pdf)  │     │  Temporal tracking      │          │
│  │  Wiki-first (free reads)│     │  Multi-hop traversal    │          │
│  │                         │     │                         │          │
│  │  "What was discussed?"  │     │  "Who decided what?"    │          │
│  │  "Find docs about X"   │     │  "How did X evolve?"    │          │
│  │  "Show me the overview" │     │  "What blocks project?" │          │
│  │                         │     │                         │          │
│  │  ~80% of queries        │     │  ~20% of queries        │          │
│  │  < 200ms, low cost      │     │  200ms-1s, medium cost  │          │
│  └────────────┬────────────┘     └────────────┬────────────┘          │
│               │                                │                       │
│               └────────────┬───────────────────┘                       │
│                            ▼                                           │
│                   ┌──────────────┐                                     │
│                   │   Response   │                                     │
│                   │  Generator   │──▶  Grounded answer + citations     │
│                   └──────────────┘                                     │
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  Slack   │    │  Ingestion   │    │   MongoDB    │                  │
│  │  Teams   │───▶│  Pipeline    │    │  (state +    │                  │
│  │  Discord │    │              │───▶│   wiki cache)│                  │
│  └──────────┘    └──────┬───────┘    └──────────────┘                  │
│                         │                                               │
│                    Writes to BOTH                                       │
│                  Weaviate AND Neo4j                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Current System Weaknesses (Lessons Learned)

Validated against the v1 codebase. Each weakness has a specific fix in v2.

### Critical
| # | Weakness | File Reference | v2 Fix |
|---|----------|---------------|--------|
| 1.11 | Cluster linking is a no-op | `consolidation.py:214-231` | Actually write `cluster_id` to atomic memories in Weaviate |
| 1.3 | Detail queries bypass hierarchy | `hierarchical_retrieval.py:199-203` | Two-stage topic-first retrieval (Solution A) |
| 1.13 | Memory quality 5.25/10 | `09-MEMORY_EVAL_PLAN.md:35` | Quality gate: reject vague facts, max 2 per message |
| 1.10 | Brittle regex classifier | `hierarchical_retrieval.py:49-120` | LLM-powered query understanding (flash-lite) |

### High
| # | Weakness | File Reference | v2 Fix |
|---|----------|---------------|--------|
| 1.4 | Temporal decay never applied | `temporal.py:153-181` | Wire `apply_temporal_decay()` into retrieval ranking |
| 1.1 | Top-down only retrieval | `hierarchical_retrieval.py:170-203` | Bidirectional expansion (up + down) |
| 1.2 | Meaningless expansion thresholds | `hierarchical_retrieval.py:176,191` | Score-based expansion (`max_score < 0.6`) |
| 1.6 | Slack only | entire codebase | Python adapter layer with NormalizedMessage |

### Medium
| # | Weakness | v2 Fix |
|---|----------|--------|
| 1.5 | No feedback loop | Citation tracking + retrieval quality metrics |
| 1.7 | No real-time sync | Optional Chat SDK webhook bridge (Phase 2) |
| 1.12 | No cross-channel search | Graph memory naturally spans channels |
| 1.14 | No adaptive alpha | Wire `get_adaptive_alpha()` (pass `alpha=None`) |
| 1.15 | No semantic dedup | Jaccard similarity dedup across tiers |

---

## 3. Dual-Memory Architecture

### 3.1 Design Principle: Separation of Concerns

Each memory system handles what it's naturally best at. **They do not duplicate each other.**

| | Semantic Memory (Weaviate) | Graph Memory (Neo4j) |
|---|---|---|
| **What it stores** | Facts, summaries, topic clusters, multimodal content | Entities, relationships, temporal evolution |
| **How it's structured** | 3-tier hierarchy (summary → topics → facts) | Flexible knowledge graph (nodes + edges) |
| **How it's queried** | BM25 + vector hybrid search | Cypher graph traversal |
| **What questions it answers** | "What was discussed about X?", "Show overview", "Find docs" | "Who decided X?", "What blocks Y?", "How did Z evolve?" |
| **Query share** | ~80% (most questions are factual/topical) | ~20% (relational/temporal) |
| **Cost** | Low (embedding search only) | Medium (graph traversal + Weaviate enrichment) |
| **Latency** | < 200ms | 200ms-1s |

**Why not just one?**
- Weaviate can't do multi-hop traversal: "Person → works on → Project → has decision → blocked by → Constraint" requires a graph
- Neo4j can't do fuzzy semantic search across 10K facts with BM25+vector hybrid ranking
- Using both gives us the best of GraphRAG (from reference papers): vector search for finding relevant content + graph traversal for navigating relationships

### 3.2 Semantic Memory: Weaviate (3-Tier, Improved)

The v1 hierarchical design was sound — the implementation was broken. v2 keeps the 3-tier architecture but fixes every weakness.

```
┌─────────────────────────────────────────────────────────────────────┐
│              SEMANTIC MEMORY: WEAVIATE (3-Tier)                      │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  TIER 0: Channel Summary                                      │  │
│  │  • Channel-level overview ("what's happening?")               │  │
│  │  • Updated by consolidation service                           │  │
│  │  • Used for wiki overview section                             │  │
│  │  • Query: "Catch me up", "Overview", "Status update"          │  │
│  │  • Access: FREE (cached, no LLM needed)                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                    consolidates from                                  │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  TIER 1: Topic Clusters                                       │  │
│  │  • Grouped memories by topic (authentication, deployment...)  │  │
│  │  • Each cluster has: summary, member_ids, topic_tags          │  │
│  │  • member_ids ACTUALLY LINKED to Tier 2 atomics (v1 fix!)    │  │
│  │  • Used for topic-level questions and wiki topic sections     │  │
│  │  • Query: "Tell me about auth", "What about deployment?"     │  │
│  │  • Access: FREE (cached, no LLM needed)                       │  │
│  │                                                                │  │
│  │  v2 FIXES:                                                     │  │
│  │  ✓ _link_memories_to_cluster() actually writes cluster_id    │  │
│  │  ✓ MERGE-based dedup prevents duplicate clusters              │  │
│  │  ✓ Two-stage topic-first retrieval (coarse → fine)           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                    consolidates from                                  │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  TIER 2: Atomic Facts                                         │  │
│  │  • Individual facts with full metadata and citations          │  │
│  │  • Named vectors: text (2048-dim), image, doc (Jina v4)      │  │
│  │  • Cross-modal search (text query → find images/PDFs)         │  │
│  │  • Quality-scored at extraction (v2: reject < 0.5)            │  │
│  │  • Linked to Neo4j via graph_entity_ids                       │  │
│  │  • Query: "What exactly did Alice say?", "Find the diagram"  │  │
│  │  • Access: PAID (uses embedding for search)                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Wiki-First Cost Optimization (preserved from v1):                  │
│  • Tier 0 + Tier 1 reads = FREE (pre-generated, cached)            │
│  • Tier 2 search = CHEAP (embedding only, ~$0.001)                  │
│  • LLM synthesis = PAID (only when needed, ~$0.02)                  │
│  • Average query cost: ~$0.01 (5x cheaper than competitors)         │
└─────────────────────────────────────────────────────────────────────┘
```

#### Weaviate Schema

```python
properties = [
    # === Core ===
    Property(name="memory", data_type=DataType.TEXT),
    Property(name="channel_id", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="source", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="platform", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="timestamp", data_type=DataType.NUMBER),

    # === Hierarchy (FIXED in v2) ===
    Property(name="tier", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="cluster_id", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="member_ids", data_type=DataType.TEXT_ARRAY, skip_vectorization=True),
    Property(name="member_count", data_type=DataType.INT),

    # === Graph Linkage (NEW) ===
    Property(name="graph_entity_ids", data_type=DataType.TEXT_ARRAY,
             description="Neo4j node IDs extracted from this memory"),

    # === Quality (NEW) ===
    Property(name="quality_score", data_type=DataType.NUMBER),

    # === Temporal (NEW) ===
    Property(name="valid_at", data_type=DataType.DATE),
    Property(name="invalid_at", data_type=DataType.DATE),

    # === Tagging ===
    Property(name="topic_tags", data_type=DataType.TEXT_ARRAY, skip_vectorization=True),
    Property(name="entity_tags", data_type=DataType.TEXT_ARRAY, skip_vectorization=True),
    Property(name="action_tags", data_type=DataType.TEXT_ARRAY, skip_vectorization=True),
    Property(name="importance", data_type=DataType.TEXT, skip_vectorization=True),

    # === Citations ===
    Property(name="message_ts", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="thread_ts", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="user_name", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="slack_user_id", data_type=DataType.TEXT, skip_vectorization=True),

    # === Files ===
    Property(name="file_id", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="filename", data_type=DataType.TEXT, skip_vectorization=True),
]
# Named vectors: text_vector, image_vector, doc_vector (2048-dim Jina v4)
```

#### Retrieval Improvements (All 15 Weaknesses Fixed)

```python
class ImprovedSemanticRetriever:
    """Weaviate retrieval with all v1 weaknesses fixed."""

    async def retrieve(self, query: str, channel_id: str,
                       query_understanding: QueryUnderstanding) -> list[dict]:

        depth = query_understanding.semantic_depth  # "overview", "topic", "detail", "auto"

        if depth == "overview":
            # Tier 0 → optional expand to Tier 1
            memories = await self._retrieve_summary(channel_id, query)
            if self._should_expand(memories, "down"):
                memories += await self._retrieve_clusters(channel_id, query)

        elif depth == "topic":
            # FIX 1.3 + 1.11: Two-stage topic-first retrieval
            # Stage 1 (coarse): Find relevant topic clusters
            clusters = await self._retrieve_clusters(
                channel_id, query,
                topic_filter=query_understanding.topics,
                alpha=None,  # FIX 1.14: Adaptive alpha
            )
            # Stage 2 (fine): Search atomics WITHIN matched clusters
            if clusters:
                member_ids = self._collect_member_ids(clusters)
                atomics = await self._retrieve_atomics_scoped(
                    channel_id, query, member_ids,
                    alpha=None,  # FIX 1.14
                )
                memories = clusters + atomics
            else:
                # No matching clusters → fall back to global atomic search
                memories = await self._retrieve_atomics(channel_id, query)

            # FIX 1.1: Bidirectional — expand UP if results are weak
            if self._should_expand(memories, "up"):
                summaries = await self._retrieve_summary(channel_id, query)
                memories = self._merge_and_rerank(memories, summaries)

        else:  # detail
            # Direct atomic search, with optional upward expansion
            memories = await self._retrieve_atomics(
                channel_id, query, alpha=None,  # FIX 1.14
            )
            # FIX 1.1: Can expand UP to clusters for broader context
            if self._should_expand(memories, "up"):
                clusters = await self._retrieve_clusters(channel_id, query)
                memories = self._merge_and_rerank(memories, clusters)

        # FIX 1.4: Apply temporal decay to ranking
        self._apply_temporal_decay(memories)

        # FIX 1.13: Quality-weighted ranking boost
        self._apply_quality_boost(memories)

        # FIX 1.15: Semantic dedup across tiers
        memories = self._semantic_dedup(memories)

        return memories[:max_results]

    def _should_expand(self, memories: list, direction: str) -> bool:
        """FIX 1.2: Score-based expansion, not count-based."""
        if not memories:
            return True
        scores = [m.get("score", 0) for m in memories]
        return max(scores) < 0.6 or (sum(scores) / len(scores)) < 0.4

    def _apply_temporal_decay(self, memories: list) -> None:
        """FIX 1.4: Actually apply the existing temporal decay function."""
        for m in memories:
            days_ago = self._days_since(m.get("timestamp"))
            decay = math.exp(-self.decay_rate * (days_ago / 30))
            m["score"] *= decay
        memories.sort(key=lambda m: m.get("score", 0), reverse=True)

    def _apply_quality_boost(self, memories: list) -> None:
        """FIX 1.13: Quality-weighted ranking — good memories score higher."""
        for m in memories:
            quality = m.get("quality_score", 0.5)
            m["score"] = m["score"] * (0.7 + 0.3 * quality)
        memories.sort(key=lambda m: m.get("score", 0), reverse=True)

    def _semantic_dedup(self, memories: list, threshold=0.85) -> list:
        """FIX 1.15: Remove near-duplicates across tiers."""
        unique = []
        for mem in memories:
            is_dup = any(
                self._jaccard_similarity(mem["memory"], e["memory"]) > threshold
                for e in unique
            )
            if not is_dup:
                unique.append(mem)
        return unique
```

#### Citation Tracking (FIX 1.5)

The response generator logs which memories were actually cited, enabling retrieval quality measurement:

```python
class ResponseGenerator:
    async def generate(self, query: str, memories: list, ...) -> Response:
        response = await self._llm_generate(query, memories)
        cited_ids = self._extract_cited_memory_ids(response)

        # Log to MongoDB for quality analysis
        await self.mongo.quality_logs.insert_one({
            "query": query,
            "route": "semantic" | "graph" | "both",
            "retrieved_count": len(memories),
            "retrieved_ids": [m["id"] for m in memories],
            "cited_ids": cited_ids,
            "precision": len(cited_ids) / max(len(memories), 1),
            "timestamp": datetime.utcnow(),
        })
        return response
```

This enables Precision@K tracking, identifying underperforming queries, and future active learning.

#### Consolidation Service (FIXED)

```python
class ConsolidationService:
    """Fixed consolidation that ACTUALLY links clusters to atomics."""

    async def _link_memories_to_cluster(self, memories, cluster_id):
        """v1: no-op. v2: ACTUALLY writes cluster_id to each atomic memory."""
        collection = self.weaviate.collections.get(COLLECTION_NAME)
        for memory in memories:
            if memory.get("id"):
                collection.data.update(
                    uuid=memory["id"],
                    properties={"cluster_id": cluster_id}
                )
        logger.info(f"Linked {len(memories)} memories to cluster {cluster_id}")

    async def _consolidate_to_clusters(self, channel_id):
        """Fixed: uses content hash to detect existing clusters and prevent duplicates."""
        unclustered = await self._get_unclustered_memories(channel_id)
        topic_groups = self._group_by_topic(unclustered)

        for topic, memories in topic_groups.items():
            if len(memories) < self.cluster_threshold:
                continue

            # Check if cluster for this topic already exists
            existing = await self._find_existing_cluster(channel_id, topic)
            if existing:
                # Update existing cluster summary + add new members
                await self._update_cluster(existing, memories)
            else:
                # Create new cluster
                cluster_id = await self._create_topic_cluster(channel_id, topic, memories)

            # THIS ACTUALLY WORKS NOW
            await self._link_memories_to_cluster(memories, cluster_id or existing["id"])

    async def _find_existing_cluster(self, channel_id, topic):
        """Prevent duplicate clusters by checking for existing topic cluster."""
        results = await hybrid_search(
            channel_id=channel_id, query=topic,
            tier_filter="tier1_cluster", topic_filter=[topic],
            limit=1, alpha=0.0,  # Pure keyword match on topic
        )
        return results[0] if results else None
```

### 3.3 Graph Memory: Neo4j (Flexible)

The graph memory captures **relationship meaning** from conversations — things that semantic search fundamentally cannot handle.

```
┌─────────────────────────────────────────────────────────────────────┐
│                GRAPH MEMORY: Neo4j (Flexible)                        │
│                                                                      │
│  PURPOSE: Capture WHO did WHAT, WHEN, and HOW things RELATE         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  GUIDED-FLEXIBLE ENTITY SCHEMA                                 │ │
│  │                                                                │ │
│  │  All nodes share a base:                                       │ │
│  │  ┌──────────────────────────────────┐                         │ │
│  │  │  name:        str    (required)  │                         │ │
│  │  │  entity_type: str    (required)  │                         │ │
│  │  │  description: str    (optional)  │                         │ │
│  │  │  channel:     str               │                         │ │
│  │  │  platform:    str               │                         │ │
│  │  │  properties:  dict   (flexible) │                         │ │
│  │  │  created_at:  datetime          │                         │ │
│  │  │  updated_at:  datetime          │                         │ │
│  │  └──────────────────────────────────┘                         │ │
│  │                                                                │ │
│  │  Core types (LLM prefers these):                              │ │
│  │  Person, Decision, Project, Technology                        │ │
│  │                                                                │ │
│  │  Extension types (LLM creates as needed):                     │ │
│  │  Team, Meeting, Artifact, Constraint, Budget, Deadline, ...   │ │
│  │                                                                │ │
│  │  Event node (episodic anchor):                                │ │
│  │  ┌──────────────────────────────────┐                         │ │
│  │  │  weaviate_id: str  → links to   │                         │ │
│  │  │               Weaviate atomic    │                         │ │
│  │  │  timestamp:   datetime           │                         │ │
│  │  │  channel:     str               │                         │ │
│  │  └──────────────────────────────────┘                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  FLEXIBLE RELATIONSHIPS                                        │ │
│  │                                                                │ │
│  │  NOT a fixed list — LLM extracts whatever relationship        │ │
│  │  best captures the meaning:                                    │ │
│  │                                                                │ │
│  │  Common patterns:                                              │ │
│  │  Person  ──DECIDED──▶       Decision                          │ │
│  │  Person  ──WORKS_ON──▶      Project                           │ │
│  │  Person  ──MEMBER_OF──▶     Team                              │ │
│  │  Decision──AFFECTS──▶       Project                           │ │
│  │  Decision──SUPERSEDES──▶    Decision  (temporal evolution)    │ │
│  │  Decision──BLOCKED_BY──▶    Constraint                        │ │
│  │  Decision──USES──▶          Technology                        │ │
│  │  Project ──DEPENDS_ON──▶    Project                           │ │
│  │  Meeting ──PRODUCED──▶      Decision                          │ │
│  │  Any     ──MENTIONED_IN──▶  Event     (episodic link)        │ │
│  │                                                                │ │
│  │  LLM can create ANY relationship type. The graph adapts       │ │
│  │  to whatever patterns exist in the organization's             │ │
│  │  conversations.                                                │ │
│  │                                                                │ │
│  │  Temporal properties on ALL relationships:                    │ │
│  │  • valid_from:  datetime                                      │ │
│  │  • valid_until: datetime (null = currently valid)             │ │
│  │  • created_at:  datetime (bi-temporal tracking)               │ │
│  │  • confidence:  float                                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  EPISODIC LINKING (graph ↔ Weaviate):                               │
│  • Every graph entity connects to Event nodes                       │
│  • Event.weaviate_id → points to atomic fact in Weaviate           │
│  • Enables: graph traversal → find entities → follow episodic      │
│    edges → retrieve original fact text + Slack citations            │
└─────────────────────────────────────────────────────────────────────┘
```

#### Neo4j Implementation

```python
class Neo4jStore:
    """Flexible graph memory — any entity type, any relationship type."""

    async def upsert_entity(self, entity: dict) -> str:
        """Create/update entity with dynamic label."""
        entity_type = entity["type"]  # "Person", "Decision", "Budget", etc.
        cypher = f"""
            MERGE (n:{entity_type} {{name: $name, channel: $channel}})
            ON CREATE SET n += $props, n.created_at = datetime()
            ON MATCH SET n += $props, n.updated_at = datetime()
            RETURN id(n) as node_id
        """
        return await self.execute(cypher,
            name=entity["name"], channel=entity.get("channel"),
            props={k: v for k, v in entity.get("properties", {}).items()
                   if v is not None},
        )

    async def upsert_relationship(self, rel: dict) -> None:
        """Create relationship with dynamic type + temporal properties."""
        rel_type = rel["type"]  # "DECIDED", "BLOCKED_BY", etc.
        cypher = f"""
            MATCH (s {{name: $source, channel: $channel}})
            MATCH (t {{name: $target, channel: $channel}})
            MERGE (s)-[r:{rel_type}]->(t)
            SET r.context = $context,
                r.valid_from = coalesce($valid_from, datetime()),
                r.created_at = datetime(),
                r.confidence = $confidence
        """
        await self.execute(cypher, **rel)

    async def create_episodic_link(self, entity_name: str, weaviate_id: str,
                                    channel: str, timestamp: float) -> None:
        """Link a graph entity to its source fact in Weaviate."""
        await self.execute("""
            MATCH (n {name: $name, channel: $channel})
            MERGE (e:Event {weaviate_id: $wid})
            ON CREATE SET e.channel = $channel, e.timestamp = $ts
            MERGE (n)-[:MENTIONED_IN]->(e)
        """, name=entity_name, channel=channel, wid=weaviate_id, ts=timestamp)

    async def traverse(self, start_entities: list[str], channel: str,
                       max_hops: int = 2) -> list[dict]:
        """Multi-hop traversal from matched entities."""
        return await self.execute("""
            MATCH path = (start)-[*1..$max_hops]-(end)
            WHERE start.name IN $entities AND start.channel = $channel
              AND all(r IN relationships(path) WHERE
                  r.valid_until IS NULL OR r.valid_until > datetime())
            RETURN path LIMIT 50
        """, entities=start_entities, channel=channel, max_hops=max_hops)

    async def temporal_chain(self, entity_name: str, channel: str) -> list[dict]:
        """Follow SUPERSEDES chains for temporal evolution."""
        return await self.execute("""
            MATCH path = (d:Decision)-[:SUPERSEDES*0..10]->(older:Decision)
            WHERE d.name CONTAINS $name AND d.channel = $channel
            RETURN path ORDER BY d.valid_from DESC
        """, name=entity_name, channel=channel)

    async def get_episodic_weaviate_ids(self, node_ids: list[int]) -> list[str]:
        """Get Weaviate IDs for enriching graph results with full text."""
        return await self.execute("""
            MATCH (n)-[:MENTIONED_IN]->(e:Event)
            WHERE id(n) IN $ids
            RETURN e.weaviate_id
        """, ids=node_ids)
```

### 3.4 How the Two Memories Connect

```
┌─────────────────────────────────────────────────────────────────────┐
│                  MEMORY INTERCONNECTION                               │
│                                                                      │
│  INGESTION (writes to BOTH):                                        │
│                                                                      │
│  Message: "Alice decided to use RS256 for JWT — blocked by          │
│            Carol's security review"                                  │
│       │                                                              │
│       ├──▶ WEAVIATE: Atomic fact stored with embedding              │
│       │    memory: "Alice decided to use RS256 for JWT,             │
│       │             blocked by Carol's security review"             │
│       │    id: uuid-abc-123                                          │
│       │    graph_entity_ids: [neo4j-1, neo4j-2, neo4j-3]           │
│       │                                                              │
│       └──▶ NEO4J: Entities + relationships extracted                │
│            Person(Alice) ──DECIDED──▶ Decision(Use RS256)           │
│            Decision(Use RS256) ──USES──▶ Technology(JWT)            │
│            Decision(Use RS256) ──BLOCKED_BY──▶ Person(Carol)        │
│            All entities ──MENTIONED_IN──▶ Event(weaviate_id:        │
│                                                uuid-abc-123)        │
│                                                                      │
│  QUERY (reads from ONE or BOTH):                                    │
│                                                                      │
│  "What was discussed about JWT?"                                    │
│    → Router: SEMANTIC → Weaviate hybrid search → fast, cheap        │
│                                                                      │
│  "Who decided to use RS256?"                                        │
│    → Router: GRAPH → Neo4j traversal:                               │
│      Decision(RS256) ←DECIDED── Person(Alice)                       │
│      → Follow episodic edge → Weaviate(uuid-abc-123) for full text │
│                                                                      │
│  "Tell me about the JWT migration"                                  │
│    → Router: BOTH (ambiguous) → run in parallel:                    │
│      Weaviate: semantic facts about JWT                             │
│      Neo4j: entities related to JWT (people, decisions, blockers)   │
│      → Merge, dedup, rank → comprehensive answer                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Smart Query Router

### 4.0 Query Decomposition (Preserved from v1)

Complex questions are decomposed into focused parallel sub-queries before routing. This was a key v1 feature that the v2 router must preserve and enhance.

```python
class QueryDecomposer:
    """Decompose complex questions into parallel sub-queries.

    Example:
    "What auth method did we decide on and how does it compare to best practices?"
    → internal_queries:
        - {"query": "authentication decision JWT", "focus": "decision"}
        - {"query": "OAuth implementation alice", "focus": "implementation"}
    → external_queries:
        - {"query": "JWT vs OAuth best practices 2025", "focus": "comparison"}
    """

    async def decompose(self, question: str) -> QueryPlan:
        """Break down a question into internal + external sub-queries."""
        # Fast path: simple questions → single internal query, no decomposition
        if self._is_simple(question):
            return QueryPlan(
                internal_queries=[{"query": question, "focus": "direct"}],
                external_queries=[],
            )

        # Complex questions → LLM decomposition (flash-lite)
        plan = await self._llm_decompose(question)
        return plan  # 2-4 internal + 0-2 external queries

DECOMPOSITION_PROMPT = """
You are a query decomposition specialist. Break down this question into
focused sub-queries that can be executed in parallel.

OUTPUT JSON:
{
    "internal_queries": [
        {"query": "specific search terms", "focus": "what this targets"}
    ],
    "external_queries": [
        {"query": "web search terms", "focus": "what to learn from web"}
    ]
}

RULES:
1. Generate 2-4 focused internal queries for different aspects
2. Generate 0-2 external queries ONLY if best practices / documentation
   comparison is needed
3. Internal queries should be keyword-focused (not full sentences)
4. If the question is simple, a single internal query suffices
"""
```

The decomposed sub-queries are then each routed independently through the Query Understanding step below, enabling parallel execution across both memory systems AND external search.

### 4.1 LLM-Powered Query Understanding

Replaces the brittle regex classifier (weakness 1.10) with an LLM call (~$0.001/query using flash-lite).

```python
QUERY_UNDERSTANDING_PROMPT = """
Classify this query for a team communication knowledge base.

Query: {query}
Channel: {channel_name}

Determine:
1. route: One of:
   - "semantic": Looking for facts, discussions, topics, documents
     Examples: "What was discussed about auth?", "Find deployment docs", "Overview"
   - "graph": Looking for entity relationships, people, decisions, temporal changes
     Examples: "Who decided X?", "What is Alice working on?", "What blocks project Y?"
   - "both": Could benefit from both fact retrieval AND relationship context
     Examples: "Tell me about the JWT migration", "What happened with the auth project?"
2. semantic_depth: "overview" | "topic" | "detail" (for Weaviate tier routing)
3. entities: Named entities mentioned (people, projects, technologies)
4. topics: Topic areas referenced
5. temporal_scope: "recent" | "any" | "historical"
6. confidence: 0.0-1.0

Output JSON.
"""
```

### 4.2 Routing Strategy: Cost-Optimized

```
┌─────────────────────────────────────────────────────────────────────┐
│                       SMART QUERY ROUTER                             │
│                                                                      │
│  User Query                                                          │
│      │                                                               │
│      ▼                                                               │
│  ┌──────────────────────────────────────┐                           │
│  │  QUERY UNDERSTANDING (LLM flash-lite)│  ~$0.001/query            │
│  │                                      │                           │
│  │  route: semantic | graph | both      │                           │
│  │  semantic_depth: overview|topic|detail│                           │
│  │  entities: ["Alice", "JWT"]          │                           │
│  │  topics: ["authentication"]          │                           │
│  │  confidence: 0.0-1.0                 │                           │
│  └──────┬──────────┬──────────┬─────────┘                           │
│         │          │          │                                      │
│    route=semantic  │     route=both                                  │
│    conf > 0.7      │     OR conf ≤ 0.7                              │
│         │     route=graph    │                                      │
│         │     conf > 0.7     │                                      │
│         ▼          ▼         ▼                                      │
│  ┌──────────┐ ┌────────┐ ┌────────────────┐                       │
│  │ SEMANTIC │ │ GRAPH  │ │ BOTH PARALLEL  │                       │
│  │ ONLY     │ │ ONLY   │ │                │                       │
│  │          │ │        │ │ Semantic  Graph│                       │
│  │ Weaviate │ │ Neo4j  │ │ search + trav. │                       │
│  │ 3-tier   │ │ + Weav.│ │ in parallel   │                       │
│  │ retrieval│ │ enrich │ │                │                       │
│  │          │ │        │ │ Merge results  │                       │
│  │ $0.001   │ │ $0.005 │ │ $0.006        │                       │
│  │ < 200ms  │ │ ~500ms │ │ ~500ms        │                       │
│  └────┬─────┘ └───┬────┘ └───────┬────────┘                       │
│       │           │              │                                  │
│       │    ┌──────┘              │                                  │
│       │    │ Fallback: if graph  │                                  │
│       │    │ results insufficient│                                  │
│       │    │ → also run semantic │                                  │
│       │    │                     │                                  │
│       └────┴─────────┬───────────┘                                  │
│                      ▼                                               │
│  ┌──────────────────────────────────────┐                           │
│  │  RESULT MERGER + RESPONSE GENERATOR  │                           │
│  │                                      │                           │
│  │  1. Deduplicate by weaviate_id      │                           │
│  │  2. Boost cross-validated results   │                           │
│  │  3. Apply temporal decay            │                           │
│  │  4. Quality-score weighted ranking  │                           │
│  │  5. Generate grounded response      │                           │
│  │     with citations (Gemini Flash)   │                           │
│  └──────────────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
```

#### Routing Decision Table

| Query Pattern | Route | Why | Cost | Latency |
|---|---|---|---|---|
| "What was discussed about auth?" | Semantic | Factual lookup → Weaviate excels | $0.001 | < 200ms |
| "Show me the overview" | Semantic (Tier 0) | Cached summary → FREE | $0 | < 50ms |
| "Tell me about deployment" | Semantic (Tier 1) | Topic cluster → FREE | $0 | < 50ms |
| "Find the architecture diagram" | Semantic (cross-modal) | Image search → Weaviate only | $0.001 | < 200ms |
| "Who decided to use JWT?" | Graph | Person→Decision traversal | $0.005 | ~500ms |
| "What is Alice working on?" | Graph | Person→Project traversal | $0.005 | ~500ms |
| "How did the auth approach evolve?" | Graph (temporal) | Decision→SUPERSEDES chain | $0.005 | ~500ms |
| "What blocks the migration?" | Graph | Project→BLOCKED_BY traversal | $0.005 | ~500ms |
| "Tell me about the JWT migration" | Both (parallel) | Needs facts AND relationships | $0.006 | ~500ms |
| "What happened with auth last week?" | Both (parallel) | Temporal + factual | $0.006 | ~500ms |

### 4.3 External Search (Tavily — Preserved from v1)

The v1 external search via Tavily is preserved in v2. It handles factual queries that require web knowledge (best practices, documentation, industry comparisons) — things NOT in the team's Slack history.

```python
class ExternalSearchService:
    """Web search via Tavily API for grounding with external knowledge.

    Why Tavily:
    - Cost-effective: 1,000 free credits/month vs $35/1K (Google)
    - Multiple tools: search, extract, crawl
    - No model restrictions: works with any LLM
    - Designed for AI/RAG: optimized for LLM consumption
    """

    async def search(self, query: str, search_depth: str = "basic",
                     max_results: int = 5, include_answer: bool = True,
                     include_domains: list[str] | None = None,
                     exclude_domains: list[str] | None = None,
                     ) -> ExternalSearchResponse:
        """Search the web. Returns results + optional AI-generated answer."""
        ...

    async def search_documentation(self, query: str,
                                    technology: str | None = None,
                                    max_results: int = 5,
                                    ) -> ExternalSearchResponse:
        """Optimized for finding API docs, tutorials, official docs."""
        ...

    async def extract_content(self, urls: list[str]) -> dict[str, str]:
        """Extract clean content from specific URLs."""
        ...
```

**Integration with Query Decomposition:**

When the `QueryDecomposer` produces `external_queries`, they are executed via Tavily in parallel with internal queries:

```
Complex Query → QueryDecomposer
  ├─ internal_queries → [routed to Semantic/Graph in parallel]
  └─ external_queries → [executed via Tavily in parallel]
      → Results merged into response context
```

**Routing decision:** The router classifies `external` queries via the decomposer, not via the query understanding LLM. Only queries that need web knowledge (comparisons, docs, best practices) generate external sub-queries.

| Config | Default |
|--------|---------|
| `TAVILY_API_KEY` | Required for external search |
| `ENABLE_EXTERNAL_SEARCH` | `true` |
| `TAVILY_SEARCH_DEPTH` | `"basic"` (1 credit) or `"advanced"` (2 credits) |
| `TAVILY_MAX_RESULTS` | `5` |

#### Graph Retrieval with Weaviate Enrichment

When the router selects Graph, Neo4j finds the relationships, then follows **episodic edges** back to Weaviate for the actual source text and citations:

```python
class GraphRetriever:
    """System-2: Neo4j traversal + Weaviate enrichment."""

    async def retrieve(self, query: str, channel_id: str,
                       understanding: QueryUnderstanding) -> list[dict]:

        # Step 1: Resolve entities from query to Neo4j nodes
        matched = await self.neo4j.fuzzy_match_entities(
            understanding.entities, channel_id
        )
        if not matched:
            return []  # No entities found → fallback to semantic

        # Step 2: Graph traversal (1-2 hops)
        if understanding.temporal_scope == "historical":
            paths = await self.neo4j.temporal_chain(matched[0], channel_id)
        else:
            paths = await self.neo4j.traverse(
                [m.name for m in matched], channel_id, max_hops=2
            )

        # Step 3: Follow episodic edges → get Weaviate memory IDs
        node_ids = self._extract_node_ids(paths)
        weaviate_ids = await self.neo4j.get_episodic_weaviate_ids(node_ids)

        # Step 4: Fetch full memories from Weaviate (text + citations)
        memories = await self.weaviate.fetch_by_ids(weaviate_ids)

        # Step 5: Combine graph structure + memory content
        return self._merge_graph_and_memories(paths, memories)
```

---

## 5. Ingestion Pipeline

### 5.1 Multi-Platform Adapters

**Chat SDK Evaluation**: The [Vercel Chat SDK](https://chat-sdk.dev/) is TypeScript-only and designed for bot webhooks — it **cannot fetch message history**. We use Python adapters for batch ingestion, with optional Chat SDK for real-time (Phase 2).

```python
@dataclass
class NormalizedMessage:
    """Unified message model across all platforms."""
    content: str
    author: AuthorInfo
    platform: Platform           # slack | teams | discord
    channel_id: str
    channel_name: str
    message_id: str
    timestamp: datetime
    thread_id: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    reactions: list[str] = field(default_factory=list)
    reply_count: int = 0
    raw_metadata: dict = field(default_factory=dict)

class BaseAdapter(ABC):
    @abstractmethod
    async def fetch_history(self, channel_id, since=None, limit=500) -> list[NormalizedMessage]: ...

class SlackAdapter(BaseAdapter):    # slack-sdk (Python)
class TeamsAdapter(BaseAdapter):    # Microsoft Graph API
class DiscordAdapter(BaseAdapter):  # discord.py
```

### 5.2 Pipeline: Writes to Both Memory Systems

```
┌─────────────────────────────────────────────────────────────────────┐
│                      INGESTION PIPELINE                              │
│                                                                      │
│  NormalizedMessage (from any adapter)                                │
│         │                                                            │
│         ▼                                                            │
│  STAGE 1: PREPROCESS                                                │
│  • Modality detection, attachment parsing, thread assembly           │
│         │                                                            │
│         ▼                                                            │
│  STAGE 2: EXTRACT + QUALITY GATE                                    │
│  • LLM fact extraction (Gemini Flash Lite)                          │
│  • Quality scoring → REJECT < 0.5, max 2 facts/message             │
│         │                                                            │
│         ▼                                                            │
│  STAGE 3: ENTITY EXTRACTION (for Graph Memory)                      │
│  • LLM extracts entities (flexible types) + relationships           │
│  • Dedup against existing graph nodes (fuzzy name match)            │
│  • Temporal validity assignment                                      │
│         │                                                            │
│         ▼                                                            │
│  STAGE 4: CLASSIFY + TAG                                            │
│  • Topic, entity, action tagging + importance scoring               │
│         │                                                            │
│         ▼                                                            │
│  STAGE 5: EMBED (Jina v4, 2048-dim, multimodal)                    │
│         │                                                            │
│         ▼                                                            │
│  STAGE 6: NOVELTY CHECK + PERSIST                                   │
│  │                                                                   │
│  ├──▶ WEAVIATE: Insert atomic fact (Tier 2)                        │
│  │    with graph_entity_ids, quality_score, embeddings              │
│  │                                                                   │
│  ├──▶ NEO4J: MERGE entities + CREATE relationships                 │
│  │    with episodic Event link (weaviate_id → fact)                 │
│  │                                                                   │
│  └──▶ MONGODB: Update sync state                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Entity Extraction Prompt (Guided-Flexible)

```python
ENTITY_EXTRACTION_PROMPT = """
Extract entities and relationships from this message.

CORE ENTITY TYPES (prefer these when applicable):
- Person: individual (fields: name, role, team)
- Decision: concrete choice (fields: summary, status, rationale, date)
- Project: initiative (fields: name, status, description)
- Technology: tool/framework (fields: name, category)

EXTENSION TYPES (use when content doesn't fit core types):
- Create any type: Team, Meeting, Artifact, Constraint, Deadline, Budget, ...

RELATIONSHIPS:
- Use descriptive verb phrases: DECIDED, WORKS_ON, BLOCKED_BY, OWNS, ...
- NOT limited to a fixed set — use whatever captures the meaning
- Include temporal context when available

EXISTING ENTITIES (reuse names to avoid duplicates):
{existing_entities}

OUTPUT JSON:
{
  "entities": [{"type": "...", "name": "...", "properties": {...}}],
  "relationships": [{"source": "...", "type": "...", "target": "...",
                      "context": "...", "temporal": "current|supersedes:<old>"}],
  "confidence": 0.0-1.0
}
"""
```

### 5.4 Quality Gate

```python
class MemoryQualityGate:
    MIN_LENGTH = 40
    MAX_FACTS_PER_MESSAGE = 2
    MIN_QUALITY_SCORE = 0.5
    VAGUE_PATTERNS = ["the user", "the process", "this was", "it was",
                      "the output", "as mentioned", "was adjusted"]

    def score_fact(self, fact: str) -> float:
        score = 1.0
        if len(fact) < self.MIN_LENGTH: score -= 0.3
        for p in self.VAGUE_PATTERNS:
            if p in fact.lower(): score -= 0.2
        if any(w[0].isupper() for w in fact.split()[1:] if len(w) > 1): score += 0.1
        if fact.startswith(("It ", "This ", "That ")): score -= 0.15
        return max(0.0, min(1.0, score))
```

---

## 6. Wiki Generation

The wiki combines both memory systems for a comprehensive view:

```markdown
# Channel Wiki: #backend-engineering

## Overview
{From Weaviate Tier 0 summary — FREE read}

## Topics
{From Weaviate Tier 1 clusters — FREE read}
### Authentication (23 memories)
  Team discussed JWT with RS256, migrated from sessions in Q3 2024...
### Infrastructure (15 memories)
  AWS EKS deployment, Terraform, ArgoCD...

## People
{From Neo4j: MATCH (p:Person)-[:MENTIONED_IN]->(e:Event {channel: $ch})}
| Person | Role | Active In | Recent Decisions |
|--------|------|-----------|-----------------|
| Alice  | Lead | Auth, API | JWT migration   |

## Decisions (Timeline)
{From Neo4j: Decision nodes with SUPERSEDES chains}
| Date | Decision | By | Status | Supersedes |
|------|----------|----|--------|------------|
| Mar 20 | Use RS256 | Alice | Active | Use HS256 |

## Recent Activity (Last 7 Days)
{From Weaviate: recent atomic memories}
```

**Cost breakdown:** Overview + Topics sections = FREE (Weaviate cache). People + Decisions = Neo4j query (~$0.001). Only the LLM synthesis costs money.

---

## 7. Research Paper Integration

| Paper | Core Insight | How v2 Uses It |
|-------|-------------|----------------|
| **GraphRAG (Weaviate+Neo4j)** | Hybrid vector-graph search | Dual memory: Weaviate for semantic, Neo4j for relational |
| **H-MEM** | 4-layer hierarchical memory | 3-tier Weaviate (summary→topic→atomic) with fixes |
| **System-1/System-2 Routing** | Dual-process retrieval | Smart router: semantic (fast) / graph (deep) / both |
| **Ebbinghaus Forgetting** | R = e^(-t/S) | Applied to retrieval ranking (actually wired in v2) |
| **MemoryBank** | Nightly distillation | Scheduled consolidation: clusters + summaries + wiki |
| **Dynamic Knowledge Graphs** | Episodic edges + fact replacement | Event nodes linking Neo4j↔Weaviate; SUPERSEDES edges |
| **Zep** | Bi-temporal tracking | valid_from/valid_until/created_at on all relationships |
| **Mem0/Mem0g** | LLM judge for consolidation | Entity extraction dedup: MERGE vs ADD vs SUPERSEDE |

---

## 8. Deployment

```yaml
# docker-compose.yml (v2)
services:
  beever-atlas:          # Python/FastAPI (MCP + REST)
    build: .
    ports: ["8000:8000"]
    depends_on: [weaviate, neo4j, mongodb]

  web:                   # React frontend
    build: ./web
    ports: ["3000:80"]

  weaviate:              # Semantic memory
    image: cr.weaviate.io/semitechnologies/weaviate:1.28.0
    ports: ["8080:8080", "50051:50051"]
    volumes: [weaviate_data:/var/lib/weaviate]

  neo4j:                 # Graph memory
    image: neo4j:5.26-community
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/beever_atlas_dev
      NEO4J_PLUGINS: '["apoc"]'
    volumes: [neo4j_data:/data]

  mongodb:               # State + cache
    image: mongo:7.0
    ports: ["27017:27017"]
    volumes: [mongo_data:/data/db]

volumes:
  weaviate_data:
  neo4j_data:
  mongo_data:
```

---

## 9. Module Structure

```
src/beever_atlas/
├── adapters/                    # Multi-platform ingestion
│   ├── base.py                  # NormalizedMessage, BaseAdapter
│   ├── slack_adapter.py         # slack-sdk
│   ├── teams_adapter.py         # Microsoft Graph API
│   └── discord_adapter.py       # discord.py
│
├── pipeline/                    # Ingestion (writes to BOTH stores)
│   ├── preprocessor.py          # Stage 1
│   ├── extractor.py             # Stage 2: facts + quality gate
│   ├── entity_extractor.py      # Stage 3: entities → Neo4j
│   ├── classifier.py            # Stage 4: tagging
│   ├── embedder.py              # Stage 5: Jina v4
│   └── persister.py             # Stage 6: write Weaviate + Neo4j + MongoDB
│
├── stores/                      # Data store clients
│   ├── weaviate_store.py        # Semantic memory (3-tier)
│   ├── neo4j_store.py           # Graph memory (flexible)
│   └── mongo_store.py           # State + wiki cache
│
├── retrieval/                   # Query system
│   ├── query_decomposer.py     # Complex question → parallel sub-queries
│   ├── query_router.py          # LLM understanding + routing
│   ├── semantic_retriever.py    # Weaviate 3-tier (improved)
│   ├── graph_retriever.py       # Neo4j traversal + Weaviate enrichment
│   ├── external_search.py       # Tavily web search (preserved from v1)
│   ├── result_merger.py         # Merge + dedup + rank
│   ├── temporal.py              # Temporal decay (ACTUALLY APPLIED)
│   ├── consolidation.py         # Cluster building (ACTUALLY LINKS)
│   └── response_generator.py    # Grounded response + citations
│
├── wiki/                        # Wiki from both memory systems
│   ├── wiki_builder.py          # Weaviate tiers + Neo4j entities → markdown
│   └── wiki_cache.py            # MongoDB cache
│
└── server/                      # Interfaces
    ├── tools.py                 # MCP tools
    ├── resources.py             # MCP resources (wiki://)
    └── api_routes.py            # REST API
```

---

## 10. Key Design Decisions

| Decision | Choice | Rationale | Rejected Alternative |
|----------|--------|-----------|---------------------|
| Memory architecture | Dual (Weaviate + Neo4j) | Each does what it's best at — semantic vs. relational | Neo4j only (can't do hybrid BM25+vector), Weaviate only (can't do multi-hop graph) |
| Weaviate tiers | Keep 3 tiers, fix bugs | Sound design; Tier 0+1 give free reads (wiki-first); just needs working cluster linking | Remove tiers (loses free wiki reads, loses topic scoping) |
| Graph schema | Guided-flexible | Core types + LLM creates extensions; captures any relationship | Fixed schema (misses Budget, Team, Meeting...), Full triplets (too noisy) |
| Relationships | Fully flexible | LLM extracts whatever verb phrase captures the meaning | Fixed relationship list (can't capture BLOCKED_BY, POSTPONED_UNTIL...) |
| Query routing | Hybrid (route OR parallel) | Semantic-first saves cost (80%); parallel for ambiguous | Pure router (misclassification), Pure parallel (wasteful) |
| Multi-platform | Python adapters | Chat SDK is TS-only, can't fetch history | Chat SDK only (no batch history) |
| Quality gate | Reject at extraction | Prevent garbage from entering system | Post-hoc cleanup (harder) |
| Cluster linking | Actually write cluster_id | v1's biggest bug — no-op | Keep as no-op (breaks everything) |

---

## 11. Open Questions

1. **Entity extraction cost**: ~$0.001/message for flash-lite. 10K messages = ~$10 initial sync. Acceptable?
2. **Graph type normalization**: How aggressively should we merge "Team"/"Group"/"Squad" into one type? LLM pass or rule-based?
3. **Consolidation frequency**: After every sync? Daily schedule? On-demand?
4. **MCP surface**: Expose graph queries as separate tools (`query_graph`) or abstract behind `ask_questions`?
5. **Chat SDK bridge**: Worth building the TypeScript webhook service for real-time ingestion in Phase 2?
6. **Decomposition threshold**: When should queries be decomposed vs. sent as-is? Token length? LLM confidence?

---

## Sources

- [Vercel Chat SDK](https://chat-sdk.dev/) — [GitHub (vercel/chat)](https://github.com/vercel/chat)
- [Chat SDK Adapters](https://chat-sdk.dev/docs/adapters) — [Changelog](https://vercel.com/changelog/chat-sdk)
- [GraphRAG via Weaviate & Neo4j](https://weaviate.io/blog/graph-rag)
- [H-MEM: Hierarchical Memory](https://arxiv.org/pdf/2507.22925)
- [System-1/System-2 Graph Retrieval](https://arxiv.org/pdf/2602.15313)
- [Zep Bi-Temporal Model](https://arxiv.org/pdf/2501.13956)
- [Mem0/Mem0g](https://arxiv.org/pdf/2504.19413)
- [Dynamic Knowledge Graphs](https://www.ijcai.org/proceedings/2025/0002.pdf)

---

*This proposal balances two complementary memory systems — Weaviate for semantic retrieval (improved 3-tier hierarchy handling 80% of queries cheaply) and Neo4j for flexible relational knowledge (handling the 20% that need entity relationships). The smart router optimizes for cost by defaulting to Weaviate-first, escalating to Neo4j only when relationships matter, and running both in parallel when the query is ambiguous.*
