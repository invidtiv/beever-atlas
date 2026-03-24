# Beever Atlas

> AI-powered memory system for team communication platforms — turning chaotic conversations into structured, searchable knowledge.

## Overview

Beever Atlas is a hierarchical memory system that ingests messages from Slack, Teams, and Discord, processes them through LLMs for fact extraction, and serves them via a dual-memory architecture combining semantic search (Weaviate) and graph relationships (Neo4j).

### Key Differentiators

| Capability | Competitors | Beever Atlas |
|------------|------------|--------------|
| **Wiki-first (FREE reads)** | Every query = LLM call | 80% free via cached wiki |
| **Dual memory (semantic + graph)** | Single memory model | Weaviate for facts + Neo4j for relationships |
| **Cross-modal search** | Text only | Text query finds images, PDFs, videos |
| **Temporal evolution** | Limited | Bi-temporal + SUPERSEDES chains |
| **Multi-platform** | Single platform | Slack, Teams, Discord |
| **Quality-gated ingestion** | Accept everything | Reject < 0.5 quality score |

### Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                      BEEVER ATLAS v2 OVERVIEW                       │
│                                                                     │
│                       ┌──────────────┐                              │
│            ┌──────────│ Smart Router  │──────────┐                  │
│            │          └──────────────┘          │                   │
│            ▼                                    ▼                   │
│  ┌───────────────────────┐     ┌───────────────────────┐           │
│  │   SEMANTIC MEMORY     │     │    GRAPH MEMORY       │           │
│  │   (Weaviate)          │     │    (Neo4j)            │           │
│  │                       │     │                       │           │
│  │  Tier 0: Summary      │     │  Flexible entities    │           │
│  │  Tier 1: Clusters     │     │  Temporal tracking    │           │
│  │  Tier 2: Atomic Facts │     │  Multi-hop traversal  │           │
│  │                       │     │                       │           │
│  │  ~80% of queries      │     │  ~20% of queries      │           │
│  │  < 200ms, low cost    │     │  200ms-1s, med cost   │           │
│  └───────────┬───────────┘     └───────────┬───────────┘           │
│              └───────────┬─────────────────┘                       │
│                          ▼                                         │
│                 ┌──────────────┐                                   │
│                 │   Response   │──▶ Grounded answer + citations    │
│                 │  Generator   │                                   │
│                 └──────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Documentation

All architecture documentation lives in `docs/improvement/`:

### Current (v2)

| Document | Description |
|----------|-------------|
| [`ARCHITECTURE_OVERVIEW_V2.md`](docs/improvement/new/ARCHITECTURE_OVERVIEW_V2.md) | Complete v2 architecture reference — dual-memory system, ingestion pipeline, query routing, deployment |
| [`TECHNICAL_PROPOSAL.md`](docs/improvement/new/TECHNICAL_PROPOSAL.md) | Design decisions and rationale for the v2 redesign |
| [`WEAKNESS_RESOLUTION_MAP.md`](docs/improvement/new/WEAKNESS_RESOLUTION_MAP.md) | Traceability matrix mapping all 15 v1 weaknesses to their v2 fixes |
| [`REFERENCE_PAPERS.md`](docs/improvement/new/REFERENCE_PAPERS.md) | Research review — GraphRAG, H-MEM, System-1/System-2 routing, Ebbinghaus forgetting, MemoryBank |

### Legacy (v1)

| Document | Description |
|----------|-------------|
| [`ARCHITECTURE_OVERVIEW.md`](docs/improvement/old/ARCHITECTURE_OVERVIEW.md) | Original v1 architecture (wiki-first, 3-tier Weaviate, multimodal) |
| [`PROJECT_ANALYSIS.md`](docs/improvement/old/PROJECT_ANALYSIS.md) | Comprehensive v1 analysis — bugs, limitations, weaknesses, priority matrix |
| [`RETRIEVAL_IMPROVEMENT_IDEAS.md`](docs/improvement/old/RETRIEVAL_IMPROVEMENT_IDEAS.md) | Validated weaknesses and proposed solutions from v1 evaluation |

## Tech Stack

- **Vector Store**: Weaviate (hybrid BM25 + vector search)
- **Graph Database**: Neo4j (entity relationships, temporal evolution)
- **Embeddings**: Jina v4 (unified multimodal embedding space)
- **LLM**: Google Gemini (fact extraction, query routing, response generation)
- **State Store**: MongoDB (metadata, wiki cache, quality metrics)
- **Platforms**: Slack, Microsoft Teams, Discord

## License

Proprietary — Votee, Inc.
