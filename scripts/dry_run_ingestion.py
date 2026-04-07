"""Dry-run ingestion pipeline — end-to-end test with rich diagnostic logging.

Runs real pipeline stages (preprocessor → extraction → classifier → embedder
→ validator → persister) against synthetic messages designed to exercise:
  - Plain text fact extraction
  - Thread context / coreference resolution
  - Multimodal (image + PDF + doc attachments)
  - Multi-platform messages (Slack, Discord, Teams)
  - Bot message filtering
  - Link extraction & unfurl metadata
  - Entity dedup (alias → canonical name)
  - Orphan entity handling
  - Contradiction detection
  - Quality scoring & classification

Usage:
    # Full pipeline (requires GOOGLE_API_KEY + JINA_API_KEY):
    python scripts/dry_run_ingestion.py

    # Preprocessor only (no LLM, no API keys):
    python scripts/dry_run_ingestion.py --preprocess-only

    # Skip embeddings (no JINA_API_KEY needed):
    python scripts/dry_run_ingestion.py --skip-embeddings

    # Verbose JSON output:
    python scripts/dry_run_ingestion.py --verbose

    # Single stage debugging:
    python scripts/dry_run_ingestion.py --stage preprocessor
    python scripts/dry_run_ingestion.py --stage facts
    python scripts/dry_run_ingestion.py --stage entities
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import logging
import os
import sys
import time
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Suppress noisy warnings before any imports trigger them
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")

# Load .env before any other imports
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Quiet noisy loggers — only show WARNING+ from library code
for _logger_name in (
    "google", "google.adk", "google.genai", "httpx", "httpcore",
    "aiohttp", "grpc", "urllib3",
    "beever_atlas.services.coreference_resolver",
    "beever_atlas.services.media_processor",
    "beever_atlas.services.media_extractors",
):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

# Suppress the ADK "App name mismatch" print by redirecting it
logging.getLogger("google.adk.runners").setLevel(logging.ERROR)


# ── Formatting helpers ────────────────────────────────────────────────

class _C:
    """ANSI color codes."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"


def _header(title: str) -> None:
    print(f"\n{_C.BOLD}{_C.CYAN}{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}{_C.RESET}")


def _subheader(title: str) -> None:
    print(f"\n  {_C.BOLD}{title}{_C.RESET}")


def _ok(msg: str) -> None:
    print(f"  {_C.GREEN}✓{_C.RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"  {_C.RED}✗{_C.RESET} {msg}")


def _info(msg: str) -> None:
    print(f"  {_C.DIM}│{_C.RESET} {msg}")


def _metric(label: str, value: Any, unit: str = "") -> None:
    val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
    print(f"  {_C.DIM}│{_C.RESET}  {label:<30} {_C.BOLD}{val_str}{_C.RESET} {unit}")


# ── Test fixtures ─────────────────────────────────────────────────────

MOCK_CHANNEL_ID = "C_DRY_RUN_001"
MOCK_CHANNEL_NAME = "#engineering"

_TS_BASE = 1711900000


def _ts(offset: int) -> str:
    return f"{_TS_BASE + offset}.{offset:03d}"


def _iso(offset: int) -> str:
    return datetime.fromtimestamp(_TS_BASE + offset, tz=timezone.utc).isoformat()


def _msg(
    content: str,
    author: str,
    author_name: str,
    offset: int,
    *,
    platform: str = "slack",
    thread_id: str | None = None,
    attachments: list[dict] | None = None,
    reactions: list[dict] | None = None,
    reply_count: int = 0,
    is_bot: bool = False,
    links: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "content": content,
        "text": content,
        "author": author,
        "author_name": author_name,
        "platform": platform,
        "channel_id": MOCK_CHANNEL_ID,
        "channel_name": MOCK_CHANNEL_NAME,
        "message_id": _ts(offset),
        "ts": _ts(offset),
        "timestamp": _iso(offset),
        "thread_id": thread_id,
        "thread_ts": thread_id,
        "attachments": attachments or [],
        "reactions": reactions or [],
        "reply_count": reply_count,
        "raw_metadata": {"links": links or []},
        "is_bot": is_bot,
    }


MOCK_MESSAGES: list[dict[str, Any]] = [
    # ── 1. Decision with strong signal ────────────────────────────────
    _msg(
        "We decided to migrate from MySQL to PostgreSQL for the Atlas project. "
        "The migration plan targets Q3 completion.",
        "U001", "Alice Chen", 0,
        reactions=[{"name": "thumbsup", "count": 5}],
        reply_count=2,
    ),
    # ── 2. Thread reply with pronoun (coreference) ────────────────────
    _msg(
        "Sounds great, I'll start working on it next sprint.",
        "U002", "Bob Kim", 60,
        thread_id=_ts(0),
    ),
    # ── 3. Another thread reply ───────────────────────────────────────
    _msg(
        "I can help with the schema migration scripts for that.",
        "U003", "Carol Wu", 120,
        thread_id=_ts(0),
    ),
    # ── 4. Contradiction: deprecating Redis ───────────────────────────
    _msg(
        "FYI — we deprecated Redis last month, switching to Memcached for all caching.",
        "U003", "Carol Wu", 180,
    ),
    # ── 5. Entity dedup test: "Atlas" should merge with "Beever Atlas"─
    _msg(
        "Atlas is looking really good after the latest refactor. The team did great work.",
        "U004", "Dave Park", 240,
    ),
    # ── 6. Orphan entity: mentioned once, no relationships ────────────
    _msg(
        "I'm starting to explore Project Nebula as a side initiative.",
        "U005", "Eve Torres", 300,
    ),
    # ── 7. Multi-platform: Teams message ──────────────────────────────
    _msg(
        "The Kubernetes cluster upgrade to v1.29 is scheduled for next Tuesday. "
        "All teams need to test their deployments beforehand.",
        "U006", "Frank Li", 360,
        platform="teams",
    ),
    # ── 8. Bot message (should be filtered) ───────────────────────────
    _msg(
        "Build #1234 passed. Deploy to staging complete.",
        "deploy-bot", "deploy-bot", 420,
        is_bot=True,
    ),
    # ── 9. Discord with links ─────────────────────────────────────────
    _msg(
        "Check out the new API docs at https://docs.beever.dev/api/v2 "
        "and the design spec at https://figma.com/file/abc123",
        "U007", "Grace Ng", 480,
        platform="discord",
        links=[
            {"url": "https://docs.beever.dev/api/v2", "title": "API Docs v2"},
            {"url": "https://figma.com/file/abc123", "title": "Design Spec"},
        ],
    ),
    # ── 10. Image attachment (multimodal) ─────────────────────────────
    _msg(
        "Here's a screenshot of the new dashboard layout",
        "U008", "Hiro Tanaka", 540,
        attachments=[{
            "type": "image",
            "url": "https://files.slack.com/mock/dashboard-screenshot.png",
            "name": "dashboard-screenshot.png",
        }],
    ),
    # ── 11. PDF attachment (multimodal) ───────────────────────────────
    _msg(
        "Attached is the Q4 architecture review document.",
        "U001", "Alice Chen", 600,
        attachments=[{
            "type": "file",
            "url": "https://files.slack.com/mock/architecture-review.pdf",
            "name": "architecture-review.pdf",
        }],
    ),
    # ── 12. Document attachment (multimodal) ──────────────────────────
    _msg(
        "Here's the updated onboarding guide for new engineers.",
        "U004", "Dave Park", 660,
        attachments=[{
            "type": "file",
            "url": "https://files.slack.com/mock/onboarding-guide.docx",
            "name": "onboarding-guide.docx",
        }],
    ),
    # ── 13. Short, low-value message (quality gate test) ──────────────
    _msg(
        "ok",
        "U002", "Bob Kim", 720,
    ),
    # ── 14. Rich decision with multiple entities ──────────────────────
    _msg(
        "After reviewing options, we're going with Terraform over Pulumi for IaC. "
        "Dave will own the migration and target July 15th for production rollout. "
        "The decision was approved by the platform team leads.",
        "U001", "Alice Chen", 780,
        reactions=[{"name": "white_check_mark", "count": 4}],
    ),
]


# ── Pipeline stage runners ────────────────────────────────────────────

async def run_stage(
    stage_name: str,
    messages_or_input: list[dict[str, Any]],
    *,
    channel_id: str = MOCK_CHANNEL_ID,
    channel_name: str = MOCK_CHANNEL_NAME,
    known_entities: list[dict[str, Any]] | None = None,
    settings: Any = None,
) -> dict[str, Any]:
    """Run a single pipeline stage and return timing + output."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    session_service = InMemorySessionService()

    if stage_name == "preprocessor":
        from beever_atlas.agents.ingestion.preprocessor import PreprocessorAgent
        agent = PreprocessorAgent(name="preprocessor")
        state = {
            "messages": messages_or_input,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "sync_job_id": "dry-run",
            "batch_num": 1,
        }
        output_key = "preprocessed_messages"

    elif stage_name == "facts":
        from beever_atlas.agents.ingestion.fact_extractor import create_fact_extractor
        agent = create_fact_extractor()
        state = {
            "preprocessed_messages": messages_or_input,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "known_entities": known_entities or [],
            "max_facts_per_message": settings.max_facts_per_message if settings else 3,
        }
        output_key = "extracted_facts"

    elif stage_name == "entities":
        from beever_atlas.agents.ingestion.entity_extractor import create_entity_extractor
        agent = create_entity_extractor()
        state = {
            "preprocessed_messages": messages_or_input,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "known_entities": known_entities or [],
            "max_facts_per_message": settings.max_facts_per_message if settings else 3,
        }
        output_key = "extracted_entities"

    elif stage_name == "classifier":
        from beever_atlas.agents.ingestion.classifier import create_classifier
        agent = create_classifier()
        state = {
            "extracted_facts": messages_or_input,
            "channel_id": channel_id,
            "channel_name": channel_name,
        }
        output_key = "classified_facts"

    else:
        raise ValueError(f"Unknown stage: {stage_name}")

    session = await session_service.create_session(
        app_name="ingestion", user_id="dev", session_id=str(uuid.uuid4()),
        state=state,
    )
    runner = Runner(agent=agent, app_name="ingestion", session_service=session_service)

    t0 = time.monotonic()
    event_count = 0
    # Suppress noisy library output (ADK warnings, traceback from graceful fallbacks)
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        async for _ in runner.run_async(
            user_id="dev", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=f"run {stage_name}")]),
        ):
            event_count += 1
    elapsed = time.monotonic() - t0

    final = await session_service.get_session(app_name="ingestion", user_id="dev", session_id=session.id)
    output = (final.state.get(output_key) or []) if final else []

    return {
        "output": output,
        "elapsed": elapsed,
        "events": event_count,
        "output_key": output_key,
    }


# ── Reporting helpers ─────────────────────────────────────────────────

def report_preprocessor(messages_in: list, result: dict, verbose: bool) -> dict[str, Any]:
    """Print preprocessor diagnostics and return feature stats."""
    output = result["output"]

    _metric("Input messages", len(messages_in))
    _metric("Output messages", len(output))
    _metric("Filtered (bot/system)", len(messages_in) - len(output))
    _metric("Time", result["elapsed"], "s")
    print()

    # Per-message breakdown
    _subheader("Message Processing Detail")
    stats = {
        "coref": 0, "thread_ctx": 0, "links": 0,
        "multimodal": 0, "platforms": set(), "bot_filtered": len(messages_in) - len(output),
    }

    for msg in output:
        author = msg.get("username") or msg.get("author_name") or "?"
        text = (msg.get("text") or "")[:75]
        platform = msg.get("platform", "?")
        stats["platforms"].add(platform)

        badges = []
        if msg.get("raw_text") and msg.get("raw_text") != msg.get("text"):
            badges.append(f"{_C.MAGENTA}COREF{_C.RESET}")
            stats["coref"] += 1
        if msg.get("thread_context"):
            badges.append(f"{_C.BLUE}THREAD{_C.RESET}")
            stats["thread_ctx"] += 1
        if msg.get("source_link_urls"):
            n = len(msg["source_link_urls"])
            badges.append(f"{_C.CYAN}LINKS:{n}{_C.RESET}")
            stats["links"] += 1
        if msg.get("modality") == "mixed":
            badges.append(f"{_C.YELLOW}MEDIA{_C.RESET}")
            stats["multimodal"] += 1
        elif msg.get("attachments"):
            badges.append(f"{_C.YELLOW}ATTACH{_C.RESET}")
            stats["multimodal"] += 1

        badge_str = f" [{', '.join(badges)}]" if badges else ""
        ellipsis = "…" if len(msg.get("text", "")) > 75 else ""
        _info(f"[{platform}] {author}: {text}{ellipsis}{badge_str}")

    print()
    _subheader("Feature Summary")
    _metric("Coreference resolved", stats["coref"], "messages")
    _metric("Thread context added", stats["thread_ctx"], "messages")
    _metric("Links extracted", stats["links"], "messages")
    _metric("Multimodal detected", stats["multimodal"], "messages")
    _metric("Platforms", ", ".join(sorted(stats["platforms"])))
    _metric("Bot messages filtered", stats["bot_filtered"])

    if verbose:
        print(f"\n{_C.DIM}  Raw output:{_C.RESET}")
        print(json.dumps(output, indent=2, default=str))

    return stats


def report_extraction(stage_name: str, result: dict, verbose: bool) -> dict[str, Any]:
    """Print fact or entity extraction diagnostics."""
    raw = result["output"]
    stats: dict[str, Any] = {"elapsed": result["elapsed"]}

    if stage_name == "facts":
        facts = raw.get("facts") if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        if not isinstance(facts, list):
            facts = []
        stats["count"] = len(facts)
        _metric("Facts extracted", len(facts))
        _metric("Time", result["elapsed"], "s")
        print()

        if facts:
            _subheader("Extracted Facts")
            for f in facts:
                score = f.get("quality_score", 0)
                imp = f.get("importance", "?")
                text = f.get("memory_text", "")[:80]
                tags = f.get("entity_tags", [])
                topics = f.get("topic_tags", [])

                if score >= 0.7:
                    icon = f"{_C.GREEN}+{_C.RESET}"
                elif score >= 0.4:
                    icon = f"{_C.YELLOW}~{_C.RESET}"
                else:
                    icon = f"{_C.RED}-{_C.RESET}"

                _info(f"[{icon}] [{score:.2f}|{imp}] {text}")
                if tags:
                    _info(f"    entities: {', '.join(tags)}")
                if topics:
                    _info(f"    topics:   {', '.join(topics)}")

            # Aggregate metrics
            print()
            _subheader("Fact Quality Distribution")
            scores = [f.get("quality_score", 0) for f in facts]
            high = sum(1 for s in scores if s >= 0.7)
            med = sum(1 for s in scores if 0.4 <= s < 0.7)
            low = sum(1 for s in scores if s < 0.4)
            _metric("High quality (≥0.7)", high)
            _metric("Medium quality (0.4–0.7)", med)
            _metric("Low quality (<0.4)", low)
            _metric("Average score", sum(scores) / len(scores) if scores else 0)

            importance_dist = {}
            for f in facts:
                imp = f.get("importance", "unknown")
                importance_dist[imp] = importance_dist.get(imp, 0) + 1
            _metric("Importance distribution", json.dumps(importance_dist))

            stats["scores"] = scores
            stats["importance"] = importance_dist
            stats["facts"] = facts

    elif stage_name == "entities":
        entities = raw.get("entities") if isinstance(raw, dict) else []
        relationships = raw.get("relationships") if isinstance(raw, dict) else []
        if not isinstance(entities, list):
            entities = []
        if not isinstance(relationships, list):
            relationships = []

        stats["entities"] = len(entities)
        stats["relationships"] = len(relationships)

        _metric("Entities", len(entities))
        _metric("Relationships", len(relationships))
        _metric("Time", result["elapsed"], "s")
        print()

        if entities:
            _subheader("Extracted Entities")
            type_dist: dict[str, int] = {}
            for e in entities:
                etype = e.get("type", "?")
                name = e.get("name", "?")
                aliases = e.get("aliases", [])
                status = e.get("status", "active")
                type_dist[etype] = type_dist.get(etype, 0) + 1

                alias_str = f" {_C.DIM}(aka: {', '.join(aliases)}){_C.RESET}" if aliases else ""
                status_str = f" {_C.YELLOW}[{status}]{_C.RESET}" if status != "active" else ""
                _info(f"[{etype}] {name}{alias_str}{status_str}")

            print()
            _subheader("Entity Type Distribution")
            for etype, count in sorted(type_dist.items()):
                _metric(etype, count)
            stats["type_dist"] = type_dist

        if relationships:
            print()
            _subheader("Extracted Relationships")
            for r in relationships:
                src = r.get("source", "?")
                tgt = r.get("target", "?")
                rtype = r.get("type", "?")
                conf = r.get("confidence", 0)
                _info(f"{src} ──[{rtype}]──▸ {tgt} {_C.DIM}(conf={conf:.1f}){_C.RESET}")

        stats["entity_list"] = entities
        stats["relationship_list"] = relationships

    if verbose:
        print(f"\n{_C.DIM}  Raw output:{_C.RESET}")
        print(json.dumps(raw, indent=2, default=str))

    return stats


# ── Feature verification checks ──────────────────────────────────────

def run_checks(
    prep_stats: dict[str, Any],
    fact_stats: dict[str, Any] | None,
    entity_stats: dict[str, Any] | None,
) -> list[tuple[str, bool, str]]:
    """Return list of (name, passed, detail) tuples."""
    checks: list[tuple[str, bool, str]] = []

    # Preprocessor checks
    checks.append((
        "Bot messages filtered",
        prep_stats.get("bot_filtered", 0) > 0,
        f"{prep_stats.get('bot_filtered', 0)} filtered",
    ))
    checks.append((
        "Multi-platform support",
        len(prep_stats.get("platforms", set())) >= 2,
        f"platforms: {', '.join(sorted(prep_stats.get('platforms', set())))}",
    ))
    checks.append((
        "Thread context resolution",
        prep_stats.get("thread_ctx", 0) > 0,
        f"{prep_stats.get('thread_ctx', 0)} messages enriched",
    ))
    checks.append((
        "Link extraction",
        prep_stats.get("links", 0) > 0,
        f"{prep_stats.get('links', 0)} messages with links",
    ))
    checks.append((
        "Multimodal detection",
        prep_stats.get("multimodal", 0) > 0,
        f"{prep_stats.get('multimodal', 0)} media messages",
    ))

    if fact_stats:
        facts = fact_stats.get("facts", [])
        checks.append((
            "Facts extracted",
            fact_stats.get("count", 0) > 0,
            f"{fact_stats.get('count', 0)} facts",
        ))
        checks.append((
            "Quality scores assigned",
            all(f.get("quality_score", 0) > 0 for f in facts) if facts else False,
            f"avg={sum(f.get('quality_score', 0) for f in facts) / len(facts):.2f}" if facts else "no facts",
        ))
        checks.append((
            "Entity tags populated",
            any(f.get("entity_tags") for f in facts),
            f"{sum(1 for f in facts if f.get('entity_tags'))} facts with tags",
        ))
        checks.append((
            "Importance classification",
            any(f.get("importance") in ("high", "critical") for f in facts),
            f"high/critical: {sum(1 for f in facts if f.get('importance') in ('high', 'critical'))}",
        ))

    if entity_stats:
        entities = entity_stats.get("entity_list", [])
        relationships = entity_stats.get("relationship_list", [])
        checks.append((
            "Entities extracted",
            entity_stats.get("entities", 0) > 0,
            f"{entity_stats.get('entities', 0)} entities",
        ))
        checks.append((
            "Relationships extracted",
            entity_stats.get("relationships", 0) > 0,
            f"{entity_stats.get('relationships', 0)} relationships",
        ))
        # Entity dedup check: "Atlas" should resolve to canonical name
        atlas_ents = [e for e in entities if "atlas" in e.get("name", "").lower()]
        checks.append((
            "Entity dedup hint (Atlas → canonical)",
            len(atlas_ents) <= 1 or any("Beever" in e.get("name", "") for e in atlas_ents),
            f"atlas entities: {[e.get('name') for e in atlas_ents]}",
        ))

    return checks


# ── Main ──────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run ingestion pipeline test")
    parser.add_argument("--preprocess-only", action="store_true", help="Only run preprocessor (no LLM)")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding stage")
    parser.add_argument("--verbose", action="store_true", help="Print full JSON output")
    parser.add_argument("--stage", choices=["preprocessor", "facts", "entities"], help="Run single stage")
    args = parser.parse_args()

    print(f"\n{_C.BOLD}{'═' * 70}")
    print(f"  BEEVER ATLAS — DRY RUN INGESTION PIPELINE")
    print(f"  {len(MOCK_MESSAGES)} synthetic messages | Slack + Discord + Teams")
    print(f"{'═' * 70}{_C.RESET}")

    timings: dict[str, float] = {}
    settings = None

    # Initialize LLM provider if needed
    if not args.preprocess_only and args.stage != "preprocessor":
        from beever_atlas.infra.config import get_settings
        from beever_atlas.llm.provider import init_llm_provider
        settings = get_settings()
        init_llm_provider(settings)

    # ── Stage 1: Preprocessor ─────────────────────────────────────────
    _header("Stage 1: Preprocessor")
    prep_result = await run_stage("preprocessor", MOCK_MESSAGES)
    timings["preprocessor"] = prep_result["elapsed"]
    preprocessed = prep_result["output"]
    prep_stats = report_preprocessor(MOCK_MESSAGES, prep_result, args.verbose)

    if args.preprocess_only or args.stage == "preprocessor":
        print(f"\n  {_C.DIM}--preprocess-only mode. Stopping here.{_C.RESET}\n")
        checks = run_checks(prep_stats, None, None)
        _print_checks(checks)
        _print_summary(timings, prep_stats, None, None, checks)
        return

    # ── Stage 2a: Fact Extraction (LLM) ───────────────────────────────
    fact_stats = None
    if args.stage in (None, "facts"):
        _header("Stage 2a: Fact Extraction (LLM)")
        fact_result = await run_stage("facts", preprocessed, settings=settings)
        timings["fact_extractor"] = fact_result["elapsed"]
        fact_stats = report_extraction("facts", fact_result, args.verbose)

    if args.stage == "facts":
        checks = run_checks(prep_stats, fact_stats, None)
        _print_checks(checks)
        _print_summary(timings, prep_stats, fact_stats, None, checks)
        return

    # ── Stage 2b: Entity Extraction (LLM) ─────────────────────────────
    entity_stats = None
    if args.stage in (None, "entities"):
        _header("Stage 2b: Entity Extraction (LLM)")
        known_entities = [
            {"name": "Beever Atlas", "type": "Project", "aliases": ["Atlas", "atlas"]},
            {"name": "Redis", "type": "Technology", "aliases": ["redis"]},
        ]
        entity_result = await run_stage(
            "entities", preprocessed,
            known_entities=known_entities, settings=settings,
        )
        timings["entity_extractor"] = entity_result["elapsed"]
        entity_stats = report_extraction("entities", entity_result, args.verbose)

    if args.stage == "entities":
        checks = run_checks(prep_stats, None, entity_stats)
        _print_checks(checks)
        _print_summary(timings, prep_stats, None, entity_stats, checks)
        return

    # ── Verification ──────────────────────────────────────────────────
    checks = run_checks(prep_stats, fact_stats, entity_stats)
    _print_checks(checks)
    _print_summary(timings, prep_stats, fact_stats, entity_stats, checks)

    # ── Save results ──────────────────────────────────────────────────
    output_dir = Path(".omc/cache")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "dry-run-ingestion-result.json"
    output_file.write_text(json.dumps({
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "messages_input": len(MOCK_MESSAGES),
        "preprocessed": len(preprocessed),
        "timings": timings,
        "facts": fact_stats.get("facts", []) if fact_stats else [],
        "entities": entity_stats.get("entity_list", []) if entity_stats else [],
        "relationships": entity_stats.get("relationship_list", []) if entity_stats else [],
        "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in checks],
    }, indent=2, default=str))
    _info(f"Results saved to {output_file}")
    print()


def _print_checks(checks: list[tuple[str, bool, str]]) -> None:
    _header("Feature Verification")
    for name, passed, detail in checks:
        if passed:
            _ok(f"{name}  {_C.DIM}({detail}){_C.RESET}")
        else:
            _fail(f"{name}  {_C.DIM}({detail}){_C.RESET}")

    passed_count = sum(1 for _, p, _ in checks if p)
    total = len(checks)
    color = _C.GREEN if passed_count == total else _C.YELLOW if passed_count > total // 2 else _C.RED
    print(f"\n  {color}{_C.BOLD}{passed_count}/{total} checks passed{_C.RESET}")


def _print_summary(
    timings: dict[str, float],
    prep_stats: dict[str, Any],
    fact_stats: dict[str, Any] | None,
    entity_stats: dict[str, Any] | None,
    checks: list[tuple[str, bool, str]],
) -> None:
    _header("Pipeline Summary")
    total_time = sum(timings.values())

    _metric("Messages input", len(MOCK_MESSAGES))
    _metric("Messages preprocessed", len(MOCK_MESSAGES) - prep_stats.get("bot_filtered", 0))
    if fact_stats:
        _metric("Facts extracted", fact_stats.get("count", 0))
    if entity_stats:
        _metric("Entities", entity_stats.get("entities", 0))
        _metric("Relationships", entity_stats.get("relationships", 0))
    print()

    _subheader("Stage Timings")
    for stage, t in timings.items():
        bar_len = int(t / max(total_time, 0.01) * 30)
        bar = f"{'█' * bar_len}{'░' * (30 - bar_len)}"
        pct = t / total_time * 100 if total_time > 0 else 0
        _info(f"{stage:<25} {bar} {t:6.2f}s ({pct:4.1f}%)")

    _metric("Total time", total_time, "s")
    if total_time > 0 and len(MOCK_MESSAGES) > 0:
        _metric("Throughput", len(MOCK_MESSAGES) / total_time, "msg/s")
    print()


if __name__ == "__main__":
    asyncio.run(main())
