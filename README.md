# Beever Atlas v2

Wiki-first RAG system with dual semantic + graph memory for Slack, Teams, and Discord.

Beever Atlas ingests messages from communication platforms, builds a persistent knowledge base using two complementary memory systems, and surfaces grounded answers with citations.

- **Semantic Memory** (Weaviate) — 3-tier hierarchical memory for factual and topic queries (~80% of queries)
- **Graph Memory** (Neo4j) — Knowledge graph for relational and temporal queries (~20% of queries)
- **Smart Router** — LLM-powered query understanding that routes to the right memory system

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   BEEVER ATLAS v2                     │
│                                                       │
│  Slack/Teams/Discord ──► Ingestion Pipeline           │
│                              │                        │
│                         Writes to BOTH                │
│                        ┌─────┴──────┐                │
│                        ▼            ▼                │
│                   Weaviate      Neo4j                │
│                  (Semantic)    (Graph)                │
│                        └─────┬──────┘                │
│                              │                        │
│  Query Router ───► Parallel Retrieval ──► Response    │
│                                                       │
│  Interfaces: FastAPI REST + MCP Server + Chat Bot     │
│  Agents: Google ADK  │  Frontend: React + shadcn/ui   │
└──────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | Google ADK (Python) |
| Chat Bot | Vercel Chat SDK (TypeScript) |
| Backend API | FastAPI |
| Semantic Store | Weaviate 1.28 |
| Graph Store | Neo4j 5.26 + APOC |
| State Store | MongoDB 7.0 |
| Session Store | Redis 7 |
| Embeddings | Jina v4 (2048-dim) |
| LLM (fast) | Gemini 2.0 Flash Lite, fallback: Claude Haiku 4.5 |
| LLM (quality) | Gemini 2.0 Flash, fallback: Claude Sonnet 4.6 |
| Frontend | React 19 + Vite + TailwindCSS + shadcn/ui |

## Prerequisites

- [Python 3.11+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Node.js 22+](https://nodejs.org/)
- [Docker](https://www.docker.com/) and Docker Compose (for infrastructure services)

## Quick Start

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd beever-atlas-v2

# Python backend
uv sync --extra dev

# React frontend
cd web && npm install && cd ..

# Bot service
cd bot && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   GOOGLE_API_KEY    — Gemini models for ADK agents
#   ANTHROPIC_API_KEY — Claude fallback via LiteLLM
#   JINA_API_KEY      — Jina v4 embeddings
#   TAVILY_API_KEY    — External web search
```

### 3. Run with Docker Compose (full stack)

```bash
docker compose up -d
```

This starts all 7 services:

| Service | Port | Description |
|---------|------|-------------|
| `beever-atlas` | 8000 | FastAPI backend |
| `web` | 3000 | React frontend |
| `weaviate` | 8080 | Semantic memory |
| `neo4j` | 7474 / 7687 | Graph memory (browser / bolt) |
| `mongodb` | 27017 | State + wiki cache |
| `redis` | 6379 | Session store |
| `bot` | — | Chat SDK bot |

### 4. Run for development (without Docker)

Start the infrastructure services first:

```bash
# Start only data stores
docker compose up -d weaviate neo4j mongodb redis
```

Then run the backend and frontend separately:

```bash
# Terminal 1 — Backend
uv run uvicorn beever_atlas.server.app:app --reload --port 8000

# Terminal 2 — Frontend
cd web && npm run dev

# Terminal 3 — Bot (optional)
cd bot && npm run dev
```

The React dev server runs on `http://localhost:5173` and proxies API calls to `http://localhost:8000`.

### 5. Verify health

```bash
curl http://localhost:8000/api/health | python3 -m json.tool
```

Returns per-component status for Weaviate, Neo4j, MongoDB, and Redis.

## Project Structure

```
beever-atlas-v2/
├── src/beever_atlas/          # Python backend
│   ├── agents/                # ADK agent definitions + tools
│   ├── adapters/              # Multi-platform ingestion (Slack, Teams, Discord)
│   ├── pipeline/              # 7-stage ingestion pipeline
│   ├── stores/                # Weaviate, Neo4j, MongoDB clients
│   ├── retrieval/             # Query routing + retrieval
│   ├── wiki/                  # Wiki generation + cache
│   ├── server/                # FastAPI app + API routes
│   └── infra/                 # Config, health, telemetry
├── web/                       # React frontend (Vite + TailwindCSS + shadcn/ui)
│   └── src/
│       ├── components/        # UI components (layout, memories, etc.)
│       ├── pages/             # Route pages
│       ├── hooks/             # React hooks
│       └── lib/               # API client, types, utilities
├── bot/                       # Chat SDK bot (TypeScript)
├── tests/                     # Python test suite
├── docs/v2/                   # Architecture and design specs
├── docker-compose.yml         # Full stack orchestration
├── Dockerfile                 # Backend container
├── pyproject.toml             # Python dependencies
└── .env.example               # Environment variable template
```

## Running Tests

```bash
# Python tests
uv run pytest tests/ -v

# Frontend type check + build
cd web && npm run build
```

## Documentation

Detailed architecture and design docs are in [`docs/v2/`](docs/v2/README.md):

1. [Architecture Overview](docs/v2/01-architecture-overview.md) — System design and dual-memory principle
2. [Semantic Memory](docs/v2/02-semantic-memory.md) — Weaviate 3-tier schema
3. [Graph Memory](docs/v2/03-graph-memory.md) — Neo4j flexible schema
4. [Query Router](docs/v2/04-query-router.md) — Smart routing and query decomposition
5. [Ingestion Pipeline](docs/v2/05-ingestion-pipeline.md) — 7-stage processing
6. [Wiki Generation](docs/v2/06-wiki-generation.md) — Cached wiki from both memory systems
7. [Deployment](docs/v2/07-deployment.md) — Docker Compose and module structure
8. [Resilience](docs/v2/08-resilience.md) — Circuit breakers and degradation
9. [Observability](docs/v2/09-observability.md) — Health, metrics, tracing
10. [Access Control](docs/v2/10-access-control.md) — Channel ACL
11. [Frontend Design](docs/v2/11-frontend-design.md) — Web dashboard UI/UX
12. [API Design](docs/v2/12-api-design.md) — REST + MCP interface spec
13. [ADK Integration](docs/v2/13-adk-integration.md) — Google ADK agent hierarchy

## License

Proprietary.
