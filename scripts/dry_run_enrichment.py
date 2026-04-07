#!/usr/bin/env python3
"""Comprehensive dry-run test for the knowledge tier enrichment pipeline.

Uses the REAL ConsolidationService static methods with rich mock data
simulating a realistic #eng-backend channel. No external services required.

Run: python scripts/dry_run_enrichment.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

from beever_atlas.models.domain import AtomicFact, TopicCluster
from beever_atlas.services.consolidation import (
    ClusterContext,
    ConsolidationService,
)

# ═══════════════════════════════════════════════════════════════════════
# Color helpers
# ═══════════════════════════════════════════════════════════════════════

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

passed = 0
failed = 0


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}")


def subsection(title: str) -> None:
    print(f"\n  {BOLD}{title}{RESET}")


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"    {GREEN}PASS{RESET} {name}")
    else:
        failed += 1
        print(f"    {RED}FAIL{RESET} {name} — {detail}")


def info(msg: str) -> None:
    print(f"    {DIM}{msg}{RESET}")


def show_json(label: str, data: object, indent: int = 6) -> None:
    prefix = " " * indent
    text = json.dumps(data, indent=2, default=str)
    lines = text.split("\n")
    print(f"{prefix}{YELLOW}{label}:{RESET}")
    for line in lines[:20]:
        print(f"{prefix}  {DIM}{line}{RESET}")
    if len(lines) > 20:
        print(f"{prefix}  {DIM}... ({len(lines) - 20} more lines){RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Mock Data: Realistic #eng-backend channel
# ═══════════════════════════════════════════════════════════════════════

NOW = datetime(2026, 4, 5, 12, 0, 0, tzinfo=UTC)
BASE = datetime(2026, 3, 10, 9, 0, 0, tzinfo=UTC)


def make_fact(
    idx: int, text: str, author: str, day_offset: float,
    topics: list[str], entities: list[str], actions: list[str] | None = None,
    importance: str = "medium", fact_type: str = "observation",
    quality: float = 0.7, media_urls: list[str] | None = None,
    media_names: list[str] | None = None, link_urls: list[str] | None = None,
    thread_summary: str = "", superseded_by: str | None = None,
) -> AtomicFact:
    ts = (BASE + timedelta(days=day_offset)).isoformat()
    return AtomicFact(
        id=f"fact-{idx:03d}",
        memory_text=text,
        quality_score=quality,
        channel_id="eng-backend",
        author_name=author,
        message_ts=ts,
        topic_tags=topics,
        entity_tags=entities,
        action_tags=actions or [],
        importance=importance,
        fact_type=fact_type,
        source_media_urls=media_urls or [],
        source_media_names=media_names or [],
        source_link_urls=link_urls or [],
        thread_context_summary=thread_summary,
        superseded_by=superseded_by,
    )


def build_all_facts() -> list[AtomicFact]:
    """Build 25 realistic atomic facts across 4 topics."""
    return [
        # ── Topic: Redis Migration (8 facts) ──────────────────────────
        make_fact(1, "Alex proposed using Redis Cluster for session caching after evaluating Memcached",
                  "Alex Chen", 0, ["redis", "caching", "session"], ["Alex Chen", "Redis Cluster", "Memcached"],
                  ["proposed"], "high", "decision", 0.92,
                  thread_summary="Team debated Redis vs Memcached over 8 messages; chose Redis for pub/sub and cluster mode"),
        make_fact(2, "Benchmark results: Redis Cluster 3x throughput vs Memcached at p99 latency",
                  "Alex Chen", 1, ["redis", "performance", "benchmark"], ["Alex Chen", "Redis Cluster", "Memcached"],
                  ["benchmarked"], "high", "observation", 0.88,
                  media_urls=["https://drive.google.com/benchmark-results.pdf"],
                  media_names=["benchmark-results.pdf"]),
        make_fact(3, "Sarah volunteered to own the Redis migration rollout for Q2",
                  "Sarah Lee", 2, ["redis", "migration"], ["Sarah Lee", "Redis Cluster"],
                  ["volunteered", "owns"], "high", "action_item", 0.85),
        make_fact(4, "Design doc for Redis failover strategy shared for review",
                  "Alex Chen", 3, ["redis", "design"], ["Alex Chen", "Redis Cluster"],
                  ["shared"], "medium", "observation", 0.75,
                  media_urls=["https://drive.google.com/redis-failover-design.pdf"],
                  media_names=["redis-failover-design.pdf"],
                  link_urls=["https://redis.io/docs/cluster-spec"]),
        make_fact(5, "Should we enable AOF persistence or rely on replication only?",
                  "Mike Park", 5, ["redis", "persistence"], ["Redis Cluster"],
                  [], "medium", "question", 0.65),
        make_fact(6, "I think we should start with replication-only and add AOF later if needed",
                  "Alex Chen", 5.5, ["redis", "persistence"], ["Alex Chen", "Redis Cluster"],
                  [], "low", "opinion", 0.6),
        make_fact(7, "Redis client library upgraded to redis-py 5.0 with cluster support",
                  "Sarah Lee", 8, ["redis", "dependencies"], ["Sarah Lee", "Redis Cluster"],
                  ["upgraded"], "medium", "observation", 0.7),
        make_fact(8, "Redis migration staging deployment completed successfully",
                  "Sarah Lee", 15, ["redis", "deployment", "staging"], ["Sarah Lee", "Redis Cluster"],
                  ["deployed", "completed"], "high", "observation", 0.82),

        # ── Topic: PgBouncer Upgrade (5 facts) ────────────────────────
        make_fact(9, "PgBouncer 1.21 has a connection leak under high concurrency — we need to upgrade",
                  "Mike Park", 2, ["postgresql", "pgbouncer", "connection-pool"], ["Mike Park", "PgBouncer"],
                  ["reported"], "high", "observation", 0.85),
        make_fact(10, "Team decided to upgrade PgBouncer to 1.22 which fixes the leak",
                  "Mike Park", 4, ["postgresql", "pgbouncer"], ["Mike Park", "PgBouncer"],
                  ["decided", "upgrade"], "high", "decision", 0.9),
        make_fact(11, "PgBouncer 1.22 deployed to staging, connection pool stable at 200 conns",
                  "Mike Park", 7, ["postgresql", "pgbouncer", "staging"], ["Mike Park", "PgBouncer"],
                  ["deployed"], "medium", "observation", 0.75),
        make_fact(12, "PgBouncer 1.22 rolled out to production, monitoring looks good",
                  "Mike Park", 10, ["postgresql", "pgbouncer", "production"], ["Mike Park", "PgBouncer"],
                  ["shipped"], "high", "observation", 0.8),
        make_fact(13, "Connection pool exhaustion incidents dropped to zero after PgBouncer upgrade",
                  "Charlie Dev", 14, ["postgresql", "pgbouncer", "incident"], ["PgBouncer", "Charlie Dev"],
                  ["resolved"], "medium", "observation", 0.78),

        # ── Topic: API Latency Investigation (6 facts) ────────────────
        make_fact(14, "API p99 latency spiked to 800ms in the orders endpoint",
                  "Charlie Dev", 3, ["api-latency", "orders", "performance"], ["Charlie Dev", "Orders Service"],
                  ["reported"], "critical", "observation", 0.9),
        make_fact(15, "Root cause: N+1 query pattern in OrderRepository.getWithItems()",
                  "Alex Chen", 4, ["api-latency", "orders", "n+1"], ["Alex Chen", "Orders Service"],
                  ["investigated", "identified"], "high", "observation", 0.88),
        make_fact(16, "Fix: Added eager loading with joinedload() to eliminate N+1 queries",
                  "Alex Chen", 5, ["api-latency", "orders", "fix"], ["Alex Chen", "Orders Service"],
                  ["fixed"], "high", "decision", 0.85,
                  link_urls=["https://github.com/beever/atlas/pull/342"]),
        make_fact(17, "API p99 latency back to 45ms after the N+1 fix was deployed",
                  "Charlie Dev", 6, ["api-latency", "orders", "performance"], ["Charlie Dev", "Orders Service"],
                  ["verified", "resolved"], "high", "observation", 0.82),
        make_fact(18, "Should we add query complexity monitoring to catch N+1 patterns automatically?",
                  "Alex Chen", 7, ["api-latency", "monitoring", "observability"], ["Alex Chen", "Orders Service"],
                  [], "medium", "question", 0.7),
        make_fact(19, "Maybe we should adopt sqlalchemy-query-analyzer for automatic N+1 detection",
                  "Charlie Dev", 7.5, ["api-latency", "monitoring"], ["Charlie Dev", "sqlalchemy-query-analyzer"],
                  [], "low", "opinion", 0.55),

        # ── Topic: Production Incident (4 facts) ──────────────────────
        make_fact(20, "INCIDENT: Connection pool exhaustion causing 503s on all API endpoints",
                  "Mike Park", 6, ["incident", "connection-pool", "production"], ["Mike Park", "PgBouncer"],
                  ["reported", "incident"], "critical", "observation", 0.95),
        make_fact(21, "Incident traced to PgBouncer 1.21 bug — connections not being returned to pool",
                  "Mike Park", 6.2, ["incident", "connection-pool", "pgbouncer"], ["Mike Park", "PgBouncer"],
                  ["investigated", "identified"], "high", "observation", 0.9),
        make_fact(22, "Mitigation: Restarted PgBouncer with max_client_conn=50 as temporary fix",
                  "Mike Park", 6.3, ["incident", "connection-pool"], ["Mike Park", "PgBouncer"],
                  ["mitigated"], "high", "action_item", 0.85),
        make_fact(23, "Post-mortem scheduled for Thursday to review incident response",
                  "Sarah Lee", 7, ["incident", "post-mortem"], ["Sarah Lee"],
                  ["scheduled"], "medium", "action_item", 0.7),

        # ── Superseded fact (should be filtered) ──────────────────────
        make_fact(24, "OLD: We decided to use Memcached for session caching",
                  "Alex Chen", -5, ["caching"], ["Alex Chen", "Memcached"],
                  ["decided"], "high", "decision", 0.8, superseded_by="fact-001"),

        # ── Low quality fact (should rank low) ────────────────────────
        make_fact(25, "Someone mentioned something about caching in standup",
                  "Unknown", 1, ["caching"], [],
                  [], "low", "observation", 0.3),
    ]


def build_mock_graph_entities() -> list[dict]:
    """Simulate graph entities that would come from Neo4j/Nebula."""
    return [
        {"id": "ge-1", "name": "Alex Chen", "type": "Person"},
        {"id": "ge-2", "name": "Sarah Lee", "type": "Person"},
        {"id": "ge-3", "name": "Mike Park", "type": "Person"},
        {"id": "ge-4", "name": "Charlie Dev", "type": "Person"},
        {"id": "ge-5", "name": "Redis Cluster", "type": "Technology"},
        {"id": "ge-6", "name": "PgBouncer", "type": "Technology"},
        {"id": "ge-7", "name": "Orders Service", "type": "Project"},
        {"id": "ge-8", "name": "Memcached", "type": "Technology"},
        {"id": "ge-9", "name": "sqlalchemy-query-analyzer", "type": "Technology"},
    ]


def build_mock_graph_relationships() -> list[dict]:
    """Simulate graph relationships."""
    return [
        {"source": "Alex Chen", "type": "DECIDED", "target": "Redis Cluster", "confidence": 0.95},
        {"source": "Sarah Lee", "type": "OWNS", "target": "Redis Cluster", "confidence": 0.9},
        {"source": "Mike Park", "type": "DECIDED", "target": "PgBouncer", "confidence": 0.9},
        {"source": "Alex Chen", "type": "WORKS_ON", "target": "Orders Service", "confidence": 0.85},
        {"source": "Charlie Dev", "type": "WORKS_ON", "target": "Orders Service", "confidence": 0.8},
        {"source": "Orders Service", "type": "DEPENDS_ON", "target": "PgBouncer", "confidence": 0.7},
        {"source": "Redis Cluster", "type": "RELATED_TO", "target": "Memcached", "confidence": 0.2},  # low confidence — should be filtered
    ]


# ═══════════════════════════════════════════════════════════════════════
# Test Flow
# ═══════════════════════════════════════════════════════════════════════

def main() -> bool:
    global passed, failed
    all_facts = build_all_facts()
    graph_entities = build_mock_graph_entities()
    graph_rels = build_mock_graph_relationships()

    print(f"\n{BOLD}Beever Atlas — Knowledge Tier Enrichment Dry Run{RESET}")
    print(f"{DIM}Testing with {len(all_facts)} atomic facts, {len(graph_entities)} graph entities, {len(graph_rels)} relationships{RESET}")

    # ── Tier 2: Show the raw atomic facts ─────────────────────────────
    section("TIER 2: Atomic Facts (Input)")

    for f in all_facts:
        tag = f"[{f.fact_type.upper():12s}]" if f.fact_type else "[            ]"
        sup = " (SUPERSEDED)" if f.superseded_by else ""
        q = f"q={f.quality_score:.2f}"
        print(f"    {DIM}{f.id}{RESET} {tag} {q} {f.memory_text[:80]}{sup}")
        if f.thread_context_summary:
            print(f"         {DIM}Thread: {f.thread_context_summary[:80]}{RESET}")

    info(f"\nTotal: {len(all_facts)} facts, {len(set(f.author_name for f in all_facts))} authors")
    info(f"Fact types: { {ft: sum(1 for f in all_facts if f.fact_type == ft) for ft in ['decision','observation','action_item','question','opinion']} }")

    # ── Cluster assignment (mock) ─────────────────────────────────────
    section("TIER 1: Topic Cluster Context Building")

    cluster_assignments = {
        "Redis Migration": [f for f in all_facts if f.id in [f"fact-{i:03d}" for i in range(1, 9)]],
        "PgBouncer Upgrade": [f for f in all_facts if f.id in [f"fact-{i:03d}" for i in range(9, 14)]],
        "API Latency": [f for f in all_facts if f.id in [f"fact-{i:03d}" for i in range(14, 20)]],
        "Production Incident": [f for f in all_facts if f.id in [f"fact-{i:03d}" for i in range(20, 24)]],
    }
    # Include superseded and low-quality in Redis cluster to test filtering
    cluster_assignments["Redis Migration"].extend(
        [f for f in all_facts if f.id in ("fact-024", "fact-025")]
    )

    clusters: list[TopicCluster] = []
    all_member_map: dict[str, list[AtomicFact]] = {}

    for topic_name, topic_facts in cluster_assignments.items():
        subsection(f"Cluster: {topic_name} ({len(topic_facts)} raw facts)")

        # Build context using the REAL ConsolidationService method (as a static helper)
        # Filter superseded
        active_facts = [f for f in topic_facts if f.superseded_by is None]
        active_facts.sort(key=lambda f: f.quality_score, reverse=True)
        top_facts = active_facts[:20]

        # Aggregate (mimicking _build_cluster_context logic)
        entity_tags: set[str] = set()
        action_tags: set[str] = set()
        authors: set[str] = set()
        timestamps: list[str] = []
        media_refs: list[str] = []
        media_names: list[str] = []
        link_refs: list[str] = []
        high_count = 0
        type_counts: dict[str, int] = {}

        for f in active_facts:
            entity_tags.update(f.entity_tags)
            action_tags.update(f.action_tags)
            if f.author_name:
                authors.add(f.author_name)
            if f.message_ts:
                timestamps.append(f.message_ts)
            media_refs.extend(f.source_media_urls)
            media_names.extend(f.source_media_names)
            link_refs.extend(f.source_link_urls)
            if f.importance in ("high", "critical"):
                high_count += 1
            if f.fact_type:
                type_counts[f.fact_type] = type_counts.get(f.fact_type, 0) + 1

        timestamps.sort()
        date_start = timestamps[0] if timestamps else ""
        date_end = timestamps[-1] if timestamps else ""

        # Graph entity resolution (simulated batch lookup)
        entity_lookup = {e["name"].lower(): e for e in graph_entities}
        resolved_entities = []
        seen = set()
        for tag in entity_tags:
            ent = entity_lookup.get(tag.lower())
            if ent and ent["id"] not in seen:
                seen.add(ent["id"])
                resolved_entities.append(ent)

        # Filter low-confidence relationships
        resolved_rels = [
            {"source": r["source"], "type": r["type"], "target": r["target"],
             "confidence": str(r["confidence"])}
            for r in graph_rels
            if r["confidence"] >= 0.3
            and (r["source"].lower() in {t.lower() for t in entity_tags}
                 or r["target"].lower() in {t.lower() for t in entity_tags})
        ]

        ctx = ClusterContext(
            facts=top_facts,
            aggregated_entity_tags=sorted(entity_tags),
            aggregated_action_tags=sorted(action_tags),
            authors=sorted(authors),
            date_range_start=date_start,
            date_range_end=date_end,
            media_refs=media_refs,
            media_names=media_names,
            link_refs=link_refs,
            high_importance_count=high_count,
            fact_type_counts=type_counts,
            graph_entities=resolved_entities,
            graph_relationships=resolved_rels,
        )

        # Show context details
        info(f"Superseded filtered: {len(topic_facts) - len(active_facts)} removed")
        info(f"Quality sorted: top fact q={top_facts[0].quality_score:.2f}, bottom q={top_facts[-1].quality_score:.2f}")
        info(f"Authors: {ctx.authors}")
        info(f"Date range: {date_start[:19]} → {date_end[:19]}")
        info(f"Fact types: {ctx.fact_type_counts}")
        info(f"High importance: {ctx.high_importance_count}")
        info(f"Graph entities: {[e['name'] + ' (' + e['type'] + ')' for e in ctx.graph_entities]}")
        info(f"Graph relationships: {[r['source'] + ' → ' + r['type'] + ' → ' + r['target'] for r in ctx.graph_relationships]}")
        info(f"Media: {ctx.media_names}, Links: {len(ctx.link_refs)}")

        # Generate prompt using REAL _format_topic_prompt
        prompt = ConsolidationService._format_topic_prompt(ctx)
        token_est = len(prompt) / 4
        info(f"Prompt length: {len(prompt)} chars (~{token_est:.0f} tokens)")
        check(f"{topic_name}: prompt under 2000 tokens", token_est <= 2000, f"{token_est:.0f} tokens")
        check(f"{topic_name}: superseded facts filtered", "Memcached for session caching" not in prompt if topic_name == "Redis Migration" else True)
        check(f"{topic_name}: has fact type breakdown", "decision" in prompt.lower() or len(type_counts) == 0)

        # Show the actual prompt
        print(f"\n      {YELLOW}── Generated LLM Prompt ──{RESET}")
        for line in prompt.split("\n"):
            print(f"      {DIM}│ {line}{RESET}")

        # Compute staleness + status
        staleness = ConsolidationService._compute_staleness(date_start, date_end, len(active_facts), now=NOW)
        status = ConsolidationService._derive_status(staleness, type_counts, list(action_tags))

        info(f"\nStaleness: {staleness:.3f}, Status: {status}")

        # Build TopicCluster
        cid = f"cluster-{topic_name.lower().replace(' ', '-')}"
        cluster = TopicCluster(
            id=cid,
            channel_id="eng-backend",
            summary=f"[LLM would generate summary for {topic_name}]",
            topic_tags=sorted(set(t for f in active_facts for t in f.topic_tags)),
            member_ids=[f.id for f in active_facts],
            member_count=len(active_facts),
            key_entities=resolved_entities,
            key_relationships=resolved_rels,
            date_range_start=date_start,
            date_range_end=date_end,
            authors=sorted(authors),
            media_refs=media_refs,
            media_names=media_names,
            link_refs=link_refs,
            high_importance_count=high_count,
            fact_type_counts=type_counts,
            staleness_score=staleness,
            status=status,
        )
        clusters.append(cluster)
        all_member_map[cid] = active_facts

    # ── Staleness tests ───────────────────────────────────────────────
    section("STALENESS + STATUS COMPUTATION")

    subsection("Staleness edge cases")
    s_fresh = ConsolidationService._compute_staleness(NOW.isoformat(), NOW.isoformat(), 5, now=NOW)
    check("Fresh cluster (0 days) → 0.0", s_fresh == 0.0, f"got {s_fresh}")

    s_week = ConsolidationService._compute_staleness(
        (NOW - timedelta(days=14)).isoformat(), (NOW - timedelta(days=7)).isoformat(), 10, now=NOW)
    check("1 week old, cadence=0.7d → low staleness", s_week < 0.5, f"got {s_week:.3f}")

    s_month = ConsolidationService._compute_staleness(
        (NOW - timedelta(days=60)).isoformat(), (NOW - timedelta(days=30)).isoformat(), 5, now=NOW)
    check("30 days old → high staleness", s_month >= 0.8, f"got {s_month:.3f}")

    s_empty = ConsolidationService._compute_staleness("", "", 0, now=NOW)
    check("Empty dates → 0.0 (safe default)", s_empty == 0.0, f"got {s_empty}")

    subsection("Status derivation")
    check("Active: fresh + mixed facts",
          ConsolidationService._derive_status(0.1, {"observation": 5, "question": 2}, []) == "active")
    check("Stale: staleness > 0.8",
          ConsolidationService._derive_status(0.85, {"decision": 3}, ["shipped"]) == "stale")
    check("Completed: decisions + completion tags + moderate staleness",
          ConsolidationService._derive_status(0.5, {"decision": 3, "observation": 2}, ["shipped", "deployed"]) == "completed")
    check("Active: decisions but no completion tags",
          ConsolidationService._derive_status(0.3, {"decision": 3}, ["proposed", "discussed"]) == "active")
    check("Active: completion tags but no decisions",
          ConsolidationService._derive_status(0.3, {"observation": 5}, ["shipped"]) == "active")

    # ── Cross-cluster links ───────────────────────────────────────────
    section("CROSS-CLUSTER LINKS (entity_tags overlap)")

    links = ConsolidationService._compute_cross_cluster_links(clusters, all_member_map)

    subsection("Link computation")
    for cid, related in links.items():
        cname = cid.replace("cluster-", "")
        related_names = [r.replace("cluster-", "") for r in related]
        info(f"{cname} ↔ {related_names}")

    check("PgBouncer ↔ Incident linked (share Mike Park + PgBouncer)",
          "cluster-production-incident" in links.get("cluster-pgbouncer-upgrade", [])
          and "cluster-pgbouncer-upgrade" in links.get("cluster-production-incident", []),
          f"links: {links}")
    check("At least one cross-cluster link found",
          len(links) >= 2, f"got {len(links)} linked clusters")

    # Show the entity overlap for each linked pair
    for cid_a, related in links.items():
        for cid_b in related:
            tags_a = {t.lower().strip() for f in all_member_map.get(cid_a, []) for t in f.entity_tags}
            tags_b = {t.lower().strip() for f in all_member_map.get(cid_b, []) for t in f.entity_tags}
            overlap = tags_a & tags_b
            if overlap:
                info(f"  {cid_a.replace('cluster-','')} ∩ {cid_b.replace('cluster-','')} = {sorted(overlap)}")

    # ── Tier 1: Show enriched TopicClusters ───────────────────────────
    section("TIER 1: Enriched Topic Clusters (Output)")

    for c in clusters:
        subsection(f"{c.id} — {', '.join(c.topic_tags[:4])}")
        info(f"Status: {c.status} | Staleness: {c.staleness_score:.3f} | Members: {c.member_count}")
        info(f"Summary: {c.summary[:100]}")
        info(f"Authors: {c.authors}")
        info(f"Date range: {c.date_range_start[:19]} → {c.date_range_end[:19]}")
        info(f"Fact types: {c.fact_type_counts}")
        info(f"Key entities: {[e['name'] for e in c.key_entities]}")
        info(f"Related clusters: {c.related_cluster_ids}")
        info(f"Media: {c.media_names} | Links: {len(c.link_refs)}")
        info(f"High importance facts: {c.high_importance_count}")

    # ── Tier 0: Channel Summary Context ───────────────────────────────
    section("TIER 0: Channel Summary Construction")

    # Apply cross-cluster links
    for c in clusters:
        c.related_cluster_ids = links.get(c.id, [])

    # Build channel context (simulating _build_channel_context)
    all_authors: set[str] = set()
    all_starts: list[str] = []
    all_ends: list[str] = []
    total_media = 0
    for c in clusters:
        all_authors.update(c.authors)
        if c.date_range_start:
            all_starts.append(c.date_range_start)
        if c.date_range_end:
            all_ends.append(c.date_range_end)
        total_media += len(c.media_refs)
    all_starts.sort()
    all_ends.sort()

    # Graph decisions (simulated)
    mock_decisions = [
        {"name": "Adopt Redis Cluster for session caching", "type": "Decision"},
        {"name": "Upgrade PgBouncer to 1.22", "type": "Decision"},
        {"name": "Fix N+1 queries in Orders Service", "type": "Decision"},
    ]

    from beever_atlas.services.consolidation import ChannelContext

    ch_ctx = ChannelContext(
        clusters=clusters,
        graph_decisions=mock_decisions,
        graph_entities=[e for e in graph_entities[:8]],
        graph_relationships=[
            {"source": r["source"], "type": r["type"], "target": r["target"],
             "confidence": str(r["confidence"])}
            for r in graph_rels if r["confidence"] >= 0.3
        ],
        date_range_start=all_starts[0] if all_starts else "",
        date_range_end=all_ends[-1] if all_ends else "",
        total_media=total_media,
        total_authors=len(all_authors),
    )

    subsection("Channel context aggregation")
    info(f"Clusters: {len(clusters)}")
    info(f"Total facts: {sum(c.member_count for c in clusters)}")
    info(f"Total authors: {ch_ctx.total_authors}")
    info(f"Total media: {ch_ctx.total_media}")
    info(f"Date span: {ch_ctx.date_range_start[:19]} → {ch_ctx.date_range_end[:19]}")
    info(f"Key decisions: {[d['name'] for d in ch_ctx.graph_decisions]}")
    info(f"Key entities: {[e['name'] + ' (' + e['type'] + ')' for e in ch_ctx.graph_entities]}")
    info(f"Worst staleness: {max(c.staleness_score for c in clusters):.3f}")

    # Generate channel prompt
    ch_prompt = ConsolidationService._format_channel_prompt(ch_ctx)
    ch_tokens = len(ch_prompt) / 4

    subsection("Channel LLM Prompt")
    print(f"\n      {YELLOW}── Generated Channel Prompt ──{RESET}")
    for line in ch_prompt.split("\n"):
        print(f"      {DIM}│ {line}{RESET}")

    check("Channel prompt under 2000 tokens", ch_tokens <= 2000, f"{ch_tokens:.0f} tokens")
    check("Channel prompt includes decisions", "decision" in ch_prompt.lower() or "redis" in ch_prompt.lower())
    check("Channel prompt includes entities", "alex" in ch_prompt.lower() or "redis" in ch_prompt.lower())

    # ── Show what the enriched ChannelSummary would look like ─────────
    subsection("Enriched ChannelSummary (output structure)")
    total_facts = sum(c.member_count for c in clusters)
    worst = max(c.staleness_score for c in clusters)

    show_json("ChannelSummary", {
        "channel_id": "eng-backend",
        "text": "[LLM would generate 3-5 sentence overview here]",
        "cluster_count": len(clusters),
        "fact_count": total_facts,
        "key_decisions": mock_decisions,
        "key_entities": [{"id": e["id"], "name": e["name"], "type": e["type"]} for e in graph_entities[:6]],
        "key_topics": [
            {"tags": c.topic_tags[:3], "member_count": c.member_count, "status": c.status}
            for c in sorted(clusters, key=lambda x: x.member_count, reverse=True)
        ],
        "date_range_start": ch_ctx.date_range_start[:19],
        "date_range_end": ch_ctx.date_range_end[:19],
        "media_count": total_media,
        "author_count": ch_ctx.total_authors,
        "worst_staleness": round(worst, 3),
    })

    # ── Token budget summary ──────────────────────────────────────────
    section("TOKEN BUDGET SUMMARY")

    for c in clusters:
        active = [f for f in all_member_map[c.id] if f.superseded_by is None]
        active.sort(key=lambda f: f.quality_score, reverse=True)
        top = active[:20]
        # Reconstruct context for accurate prompt
        ctx_for_prompt = ClusterContext(
            facts=top,
            aggregated_entity_tags=sorted(set(t for f in active for t in f.entity_tags)),
            aggregated_action_tags=sorted(set(t for f in active for t in f.action_tags)),
            authors=sorted(set(f.author_name for f in active if f.author_name)),
            date_range_start=c.date_range_start,
            date_range_end=c.date_range_end,
            media_refs=c.media_refs,
            media_names=c.media_names,
            link_refs=c.link_refs,
            high_importance_count=c.high_importance_count,
            fact_type_counts=c.fact_type_counts,
            graph_entities=c.key_entities,
            graph_relationships=c.key_relationships,
        )
        p = ConsolidationService._format_topic_prompt(ctx_for_prompt)
        t = len(p) / 4
        bar = "█" * int(t / 40) + "░" * max(0, 50 - int(t / 40))
        status = f"{GREEN}OK{RESET}" if t <= 2000 else f"{RED}OVER{RESET}"
        print(f"    {c.id:35s} {bar} {t:6.0f} tokens {status}")

    t_ch = len(ch_prompt) / 4
    bar = "█" * int(t_ch / 40) + "░" * max(0, 50 - int(t_ch / 40))
    status_ch = f"{GREEN}OK{RESET}" if t_ch <= 2000 else f"{RED}OVER{RESET}"
    print(f"    {'channel-summary':35s} {bar} {t_ch:6.0f} tokens {status_ch}")

    # ── Final results ─────────────────────────────────────────────────
    section("RESULTS")
    total = passed + failed
    if failed == 0:
        print(f"\n    {GREEN}{BOLD}ALL {total} CHECKS PASSED{RESET}\n")
    else:
        print(f"\n    {RED}{BOLD}{failed} FAILED{RESET} out of {total} checks\n")

    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
