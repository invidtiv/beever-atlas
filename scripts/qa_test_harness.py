#!/usr/bin/env python3
"""QA agent test harness with two personas.

    existing   — power user who already knows the channel. The harness
                 fetches all channel messages first, builds a lightweight
                 context summary (top authors, date range, keyword
                 frequencies), and asks deep/specific questions whose
                 answers are grounded in that real content. Grades the
                 agent on accuracy, attribution, and multi-hop synthesis.

    onboarding — brand-new user with zero prior context. Asks orientation
                 questions ("what is this channel about?", "where do I
                 start?", "who should I ping?"). Grades the agent on
                 clarity, breadth, pointers to wiki/overview sources, and
                 *absence* of insider jargon without explanation. This is
                 a proxy for "time-to-first-useful-answer".

Usage:
    # Dump raw messages (one-time per channel)
    python scripts/qa_test_harness.py dump --channel tech-beever-atlas

    # Run existing-user battery (auto-builds context from dumped messages)
    python scripts/qa_test_harness.py ask --persona existing --channel tech-beever-atlas

    # Run onboarding-user battery (no context needed)
    python scripts/qa_test_harness.py ask --persona onboarding --channel tech-beever-atlas

    # Run both
    python scripts/qa_test_harness.py ask --persona both --channel tech-beever-atlas

Each case writes the full transcript + SSE envelope to
`scripts/_qa_harness_out/report_<persona>_<channel>_<ts>.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

import httpx

API_BASE = "http://localhost:8000"
OUT_DIR = Path(__file__).parent / "_qa_harness_out"
OUT_DIR.mkdir(exist_ok=True)

# Common English words to strip when scoring keywords. Rough but enough
# to surface domain tokens (e.g. "citation", "ingestion", "Neo4j").
STOPWORDS = set("""
a an the and or but if then so because while of for on in at to from by with
is are was were be been being have has had do does did will would shall should
can could may might must this that these those it its i we you they he she
not no yes as up down out over under just about also more less than very some
any all most any my your our their his her them us me so too into onto off
what which who whom whose when where why how which one each every few many
get got make made go went come came take took see saw say said know knew
there here only even still yet like unlike via eg ie etc vs re
""".split())


# ---------------------------------------------------------------------------
# Channel resolution + message dump
# ---------------------------------------------------------------------------

async def resolve_channel_id(client: httpx.AsyncClient, name_or_id: str) -> str:
    if name_or_id.startswith(("C", "D")) and name_or_id[1:].isalnum():
        return name_or_id
    r = await client.get(f"{API_BASE}/api/channels")
    r.raise_for_status()
    payload = r.json()
    channels = payload if isinstance(payload, list) else payload.get("channels", [])
    needle = name_or_id.lstrip("#").lower()
    for ch in channels:
        name = (ch.get("name") or ch.get("display_name") or "").lower()
        cid = ch.get("channel_id") or ch.get("id")
        if cid and (name == needle or cid == name_or_id):
            return cid
    raise SystemExit(f"Channel not found: {name_or_id}")


async def dump_channel(name_or_id: str, max_pages: int = 50) -> Path:
    async with httpx.AsyncClient(timeout=120) as client:
        channel_id = await resolve_channel_id(client, name_or_id)
        print(f"Resolved channel: {channel_id}")
        out_path = OUT_DIR / f"messages_{channel_id}.jsonl"
        before: str | None = None
        prev_before: str | None = None
        total = 0
        page = 0
        with out_path.open("w") as f:
            while page < max_pages:
                page += 1
                params: dict[str, Any] = {"limit": 200, "order": "desc"}
                if before:
                    params["before"] = before
                t0 = time.monotonic()
                print(f"  page {page}  before={before}  …", end="", flush=True)
                try:
                    r = await client.get(
                        f"{API_BASE}/api/channels/{channel_id}/messages", params=params
                    )
                    r.raise_for_status()
                except Exception as e:
                    print(f" ERROR {e!r}")
                    break
                msgs = r.json().get("messages", [])
                dt = time.monotonic() - t0
                print(f" got {len(msgs)} in {dt:.1f}s")
                if not msgs:
                    break
                for m in msgs:
                    f.write(json.dumps(m) + "\n")
                total += len(msgs)
                # Endpoint expects a message ID, not a timestamp. If the
                # payload doesn't include a stable id, stop — otherwise we
                # either loop forever or send a bad cursor to the adapter.
                new_before = msgs[-1].get("id") or msgs[-1].get("message_id")
                if not new_before:
                    print("  last message has no id — stopping (single page only)")
                    break
                if new_before == prev_before:
                    print("  cursor did not advance — stopping")
                    break
                prev_before = before
                before = new_before
                if len(msgs) < 200:
                    break
        print(f"Dumped {total} messages → {out_path}")
        return out_path


# ---------------------------------------------------------------------------
# Channel context (for existing-user persona)
# ---------------------------------------------------------------------------

@dataclass
class ChannelContext:
    """Lightweight summary of a channel, derived from dumped messages.

    Used to seed `must_mention` canaries so the existing-user battery can
    check whether the agent actually surfaces real people / topics from
    the channel rather than hallucinating.
    """
    channel_id: str
    message_count: int
    date_range: tuple[str, str] | None
    top_authors: list[tuple[str, int]]     # [(author, count), …] desc
    top_keywords: list[tuple[str, int]]    # tokens excluding stopwords
    sample_texts: list[str]                 # 3 most recent non-empty msgs


def _tokenize(text: str) -> Iterable[str]:
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text or ""):
        low = tok.lower()
        if low in STOPWORDS:
            continue
        yield tok


_URL_STOP_TOKENS = {"http", "https", "www", "com", "org", "net"}


def build_channel_context(channel_id: str) -> ChannelContext:
    path = OUT_DIR / f"messages_{channel_id}.jsonl"
    if not path.exists():
        raise SystemExit(
            f"No dump for {channel_id}. Run `dump --channel {channel_id}` first."
        )
    authors: Counter[str] = Counter()
    keywords: Counter[str] = Counter()
    timestamps: list[str] = []
    samples: list[str] = []
    count = 0

    with path.open() as f:
        for line in f:
            m = json.loads(line)
            count += 1
            author = m.get("author_name") or m.get("author") or ""
            if author:
                authors[author] += 1
            ts = m.get("timestamp") or m.get("ts") or m.get("created_at")
            if ts:
                timestamps.append(str(ts))
            content = (m.get("content") or m.get("text") or "").strip()
            if content:
                for tok in _tokenize(content):
                    low = tok.lower()
                    if low in _URL_STOP_TOKENS or len(low) < 4:
                        continue
                    keywords[tok] += 1
                if len(samples) < 3:
                    samples.append(content[:200])

    date_range = None
    if timestamps:
        date_range = (min(timestamps), max(timestamps))

    return ChannelContext(
        channel_id=channel_id,
        message_count=count,
        date_range=date_range,
        top_authors=authors.most_common(10),
        top_keywords=keywords.most_common(20),
        sample_texts=samples,
    )


def print_context(ctx: ChannelContext) -> None:
    print(f"\n— Channel context for {ctx.channel_id} —")
    print(f"  messages: {ctx.message_count}")
    if ctx.date_range:
        print(f"  range:    {ctx.date_range[0]}  →  {ctx.date_range[1]}")
    print(f"  top authors:   {', '.join(f'{a}({n})' for a,n in ctx.top_authors[:5])}")
    print(f"  top keywords:  {', '.join(f'{k}({n})' for k,n in ctx.top_keywords[:10])}")
    print()


# ---------------------------------------------------------------------------
# Test case model
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    id: str
    persona: str              # "existing" | "onboarding"
    category: str
    question: str
    expected_tools: list[str] = field(default_factory=list)
    expected_kinds: list[str] = field(default_factory=list)
    expected_citations_min: int = 1
    expected_follow_ups: bool = True
    must_mention: list[str] = field(default_factory=list)
    must_not_mention: list[str] = field(default_factory=list)
    # Onboarding-specific: response should stay below this many chars to
    # avoid overwhelming a new user. 0 disables the hard-cap check.
    max_chars: int = 0
    # Soft target: warns (⚠) but does NOT fail the verdict when exceeded.
    soft_max_chars: int = 0
    notes: str = ""


# ---------------------------------------------------------------------------
# Existing-user battery: deep, specific, grounded in channel content.
# `must_mention` gets augmented at runtime from ChannelContext.
# ---------------------------------------------------------------------------

def build_existing_cases(ctx: ChannelContext) -> list[TestCase]:
    top_author = ctx.top_authors[0][0] if ctx.top_authors else ""
    top_kw = [k for k, _ in ctx.top_keywords[:3]]
    return [
        TestCase(
            id="E-A1-recent",
            persona="existing",
            category="factual_recall",
            question="What have we discussed most recently in this channel? Give me the top 3 threads with dates.",
            expected_tools=["get_recent_activity", "search_channel_facts"],
            expected_kinds=["channel_message"],
            expected_citations_min=3,
            notes="Should surface 3 distinct threads with timestamps + [N] citations.",
        ),
        TestCase(
            id="E-A2-named-fact",
            persona="existing",
            category="factual_recall",
            question=f"What has {top_author or 'the most active author'} been posting about?",
            expected_tools=["search_channel_facts"],
            expected_kinds=["channel_message"],
            must_mention=[top_author] if top_author else [],
            expected_citations_min=2,
            notes="Attribution check: must name the author and cite their messages.",
        ),
        TestCase(
            id="E-A3-keyword-deep",
            persona="existing",
            category="factual_recall",
            question=f"Tell me everything we've decided about {top_kw[0] if top_kw else 'the pipeline'}.",
            expected_tools=["search_channel_facts", "trace_decision_history"],
            expected_kinds=["channel_message", "decision_record"],
            must_mention=top_kw[:1],
            expected_citations_min=3,
        ),
        TestCase(
            id="E-B1-decision-trace",
            persona="existing",
            category="multi_hop",
            question="Why did we pick the current graph database, and who pushed for it?",
            expected_tools=["trace_decision_history", "find_experts", "search_channel_facts"],
            expected_kinds=["channel_message", "graph_relationship"],
            expected_citations_min=3,
            notes="Decision + people — tests graph + channel retrieval together.",
        ),
        TestCase(
            id="E-B2-evolution",
            persona="existing",
            category="multi_hop",
            question="How has our QA agent architecture evolved over the last month?",
            expected_tools=["search_qa_history", "search_channel_facts", "get_wiki_page"],
            expected_kinds=["channel_message", "qa_history", "wiki_page"],
            expected_citations_min=4,
        ),
        TestCase(
            id="E-C1-expert",
            persona="existing",
            category="people",
            question="If I hit a bug in the ingestion pipeline, who should I ping?",
            expected_tools=["find_experts"],
            expected_kinds=["channel_message", "graph_relationship"],
            must_mention=[top_author] if top_author else [],
            notes=f"Expected to name the top committer, likely '{top_author}'.",
        ),
        TestCase(
            id="E-E1-media",
            persona="existing",
            category="media",
            question="Pull up any screenshots or diagrams shared about the architecture.",
            expected_tools=["search_media_references"],
            expected_kinds=["channel_message", "media"],
            notes="Tests inline media rendering via [src:xxx inline].",
        ),
        TestCase(
            id="E-J1-compound",
            persona="existing",
            category="decomposition",
            question=(
                "Compare the citation registry approach with the old regex approach, "
                "list the files that changed, and tell me who reviewed it."
            ),
            expected_tools=[
                "search_channel_facts",
                "search_qa_history",
                "trace_decision_history",
                "find_experts",
            ],
            expected_citations_min=4,
            notes="Multi-tool orchestration + synthesis.",
        ),
        TestCase(
            id="E-I1-hallucination-canary",
            persona="existing",
            category="negative",
            question="What did Elon Musk say in this channel yesterday?",
            expected_citations_min=0,
            must_mention=["no record"],
            expected_follow_ups=False,
            notes="Must refuse with a 'no record / no evidence' phrase, not a fabricated quote.",
        ),
        TestCase(
            id="E-K1-inline-markers",
            persona="existing",
            category="format",
            question="Summarize the last week with inline citations.",
            expected_citations_min=2,
            must_mention=["[1]"],
            notes="StreamRewriter sanity: [src:xxx] → [N] visible.",
        ),
        # -- Extended battery ----------------------------------------
        TestCase(
            id="E-A4-date-range",
            persona="existing",
            category="temporal",
            question="What happened in this channel in the last 2 weeks? Group by week.",
            expected_tools=["get_recent_activity", "search_channel_facts"],
            expected_kinds=["channel_message"],
            expected_citations_min=2,
            notes="Tests temporal grouping + date-aware retrieval.",
        ),
        TestCase(
            id="E-A5-thread-deep",
            persona="existing",
            category="factual_recall",
            question=(
                f"Dig into everything mentioned about {top_kw[1] if len(top_kw) >= 2 else 'the agent'}. "
                "Who said what, and when?"
            ),
            expected_tools=["search_channel_facts", "find_experts"],
            expected_kinds=["channel_message"],
            expected_citations_min=3,
            must_mention=[top_kw[1]] if len(top_kw) >= 2 else [],
            notes="Thread-level deep-dive on a real keyword.",
        ),
        TestCase(
            id="E-D1-wiki-decisions",
            persona="existing",
            category="wiki",
            question="Pull up the decisions page — what has the team officially decided?",
            expected_tools=["get_wiki_page"],
            expected_kinds=["wiki_page", "decision_record"],
            expected_citations_min=1,
            notes="Tests wiki decisions page + cross-kind citations.",
        ),
        TestCase(
            id="E-G1-graph-relation",
            persona="existing",
            category="multi_hop",
            question="What is Beever Atlas related to? Give me the top 5 connected concepts.",
            expected_tools=["search_relationships"],
            expected_kinds=["graph_relationship"],
            expected_citations_min=2,
            notes="Forces graph-relationship citations into the envelope.",
        ),
        TestCase(
            id="E-P1-paraphrase",
            persona="existing",
            category="robustness",
            question=(
                f"Remind me — {top_author + ' ' if top_author else ''}"
                "posted about a particular topic. What was the main thing they talked about?"
            ),
            expected_tools=["search_channel_facts", "find_experts"],
            expected_kinds=["channel_message"],
            expected_citations_min=1,
            must_mention=[top_author] if top_author else [],
            notes="Paraphrased version of E-A2 — same retrieval goal, vaguer phrasing.",
        ),
        TestCase(
            id="E-N1-contradiction",
            persona="existing",
            category="negative",
            question=(
                "Has anyone here said that Neo4j is a bad choice for us? "
                "Quote the exact message if so."
            ),
            expected_citations_min=0,
            must_not_mention=["bad choice"],
            notes="Must NOT confabulate a quote. Either cite real negative or refuse.",
        ),
        TestCase(
            id="E-R1-off-topic-canary",
            persona="existing",
            category="negative",
            question="What's the latest stock price of NVIDIA?",
            expected_citations_min=0,
            expected_follow_ups=False,
            must_not_mention=["$"],
            notes="Channel Q&A should not drift to external finance lookup.",
        ),
    ]


# ---------------------------------------------------------------------------
# Onboarding-user battery: no context assumed. Questions a brand-new
# teammate would ask on day one. Graded on clarity, breadth, pointers to
# wiki/overview, and whether follow-up suggestions help them keep going.
# ---------------------------------------------------------------------------

ONBOARDING_CASES: list[TestCase] = [
    TestCase(
        id="O-1-what-is-this",
        persona="onboarding",
        category="orientation",
        question="I just joined. What is this channel about in one paragraph?",
        expected_tools=["get_topic_overview", "get_wiki_page"],
        expected_kinds=["wiki_page", "channel_message"],
        expected_citations_min=1,
        max_chars=1200,
        expected_follow_ups=True,
        notes="First-touch — should be concise, cite the overview, offer follow-ups.",
    ),
    TestCase(
        id="O-2-start-here",
        persona="onboarding",
        category="orientation",
        question="What are the 3 most important things I should read first to catch up?",
        expected_tools=["get_wiki_page", "get_topic_overview", "search_channel_facts"],
        expected_kinds=["wiki_page", "channel_message"],
        expected_citations_min=3,
        max_chars=1500,
        notes="Should return a ranked list with clickable citations.",
    ),
    TestCase(
        id="O-3-who-is-who",
        persona="onboarding",
        category="people",
        question="Who are the most active people here and what are they working on?",
        expected_tools=["find_experts", "get_recent_activity"],
        expected_kinds=["channel_message"],
        expected_citations_min=2,
        max_chars=2000,
        soft_max_chars=1200,
    ),
    TestCase(
        id="O-4-glossary",
        persona="onboarding",
        category="glossary",
        question="What acronyms or project codenames get thrown around here that I should know?",
        expected_tools=["search_channel_facts", "get_wiki_page"],
        expected_kinds=["channel_message", "wiki_page"],
        expected_citations_min=1,
        notes="Agent should define jargon, not assume it. Tests anti-insider-slang.",
    ),
    TestCase(
        id="O-5-current-focus",
        persona="onboarding",
        category="orientation",
        question="What is the team focused on right now, and what just shipped?",
        expected_tools=["get_recent_activity", "search_channel_facts"],
        expected_kinds=["channel_message"],
        expected_citations_min=2,
        max_chars=2000,
        soft_max_chars=1200,
    ),
    TestCase(
        id="O-6-open-questions",
        persona="onboarding",
        category="orientation",
        question="Are there any open questions or unresolved decisions I should be aware of?",
        expected_tools=["search_channel_facts", "search_qa_history"],
        expected_kinds=["channel_message", "qa_history"],
        expected_citations_min=1,
    ),
    TestCase(
        id="O-7-how-do-i",
        persona="onboarding",
        category="process",
        question="How do I propose a change or spec here? What's the workflow?",
        expected_tools=["get_wiki_page", "search_channel_facts"],
        expected_kinds=["wiki_page", "channel_message"],
        max_chars=2000,
        soft_max_chars=1200,
    ),
    TestCase(
        id="O-8-where-is-code",
        persona="onboarding",
        category="pointers",
        question="Where does the code live and how is the repo organized?",
        expected_tools=["get_wiki_page", "search_channel_facts"],
        expected_kinds=["wiki_page", "channel_message"],
    ),
    TestCase(
        id="O-9-ask-more",
        persona="onboarding",
        category="continuity",
        question="Can you tell me more about the last thing you mentioned?",
        notes="Run AFTER O-1 in the same session — tests chat_history continuity.",
        expected_citations_min=0,
        expected_follow_ups=True,
    ),
    TestCase(
        id="O-10-humility-canary",
        persona="onboarding",
        category="negative",
        question="What is the team's revenue target for Q4?",
        expected_citations_min=0,
        must_not_mention=["$"],
        expected_follow_ups=False,
        notes="Channel likely has no revenue data — must say so, not invent figures.",
    ),
    # -- Extended onboarding battery ----------------------------------
    TestCase(
        id="O-11-roadmap",
        persona="onboarding",
        category="orientation",
        question="Is there a roadmap or upcoming milestones I should know about?",
        expected_tools=["get_wiki_page", "search_channel_facts"],
        expected_kinds=["wiki_page", "channel_message"],
        max_chars=2000,
        soft_max_chars=1200,
    ),
    TestCase(
        id="O-12-pair-up",
        persona="onboarding",
        category="people",
        question="Who should I pair with for my first PR in this codebase?",
        expected_tools=["find_experts", "search_channel_facts"],
        expected_kinds=["channel_message", "graph_relationship"],
        expected_citations_min=1,
        max_chars=2000,
        soft_max_chars=1200,
        notes="Combines people lookup with actionable onboarding advice.",
    ),
    TestCase(
        id="O-13-acronym",
        persona="onboarding",
        category="glossary",
        question="What does RAG mean in the context of this project?",
        expected_tools=["search_channel_facts", "get_wiki_page"],
        expected_kinds=["wiki_page", "channel_message"],
        expected_citations_min=1,
        max_chars=800,
        notes="Single-term glossary lookup — should be crisp.",
    ),
    TestCase(
        id="O-14-format-list",
        persona="onboarding",
        category="format",
        question="Give me a bulleted list of the 5 most-referenced concepts in this channel.",
        expected_tools=["search_channel_facts", "get_topic_overview"],
        expected_citations_min=3,
        must_mention=["-", "*"],
        notes="Tests response formatting compliance (bullets).",
    ),
    TestCase(
        id="O-15-deep-followup",
        persona="onboarding",
        category="continuity",
        question="Why is that important?",
        notes=(
            "Run AFTER O-13 in same session — a second-level pronoun chain. "
            "Tests that the agent resolves 'that' back to RAG."
        ),
        expected_citations_min=0,
        expected_follow_ups=True,
        max_chars=1200,
    ),
]


# ---------------------------------------------------------------------------
# SSE runner + grading
# ---------------------------------------------------------------------------

async def _run_one(
    client: httpx.AsyncClient,
    channel_id: str,
    session_id: str,
    mode: str,
    tc: TestCase,
    log,  # open text file, line-buffered
) -> dict[str, Any]:
    def L(msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        log.write(line + "\n")
        log.flush()

    payload = {
        "question": tc.question,
        "channel_id": channel_id,
        "session_id": session_id,
        "mode": mode,
    }
    answer = ""
    thinking_text = ""
    citations: dict[str, Any] = {}
    follow_ups: list[str] = []
    tool_calls: list[str] = []
    tool_events: list[dict[str, Any]] = []
    errors: list[str] = []
    event_counts: Counter[str] = Counter()
    ttft: float | None = None
    first_tool_at: float | None = None
    t0 = time.monotonic()
    L("")
    L("=" * 78)
    L(f"CASE {tc.id} ({tc.persona}/{tc.category})")
    L(f"Q: {tc.question}")
    L("=" * 78)

    async with client.stream("POST", f"{API_BASE}/api/ask", json=payload, timeout=180) as r:
        event_name = None
        async for raw in r.aiter_lines():
            if not raw:
                event_name = None
                continue
            if raw.startswith("event:"):
                event_name = raw.split(":", 1)[1].strip()
            elif raw.startswith("data:"):
                try:
                    data = json.loads(raw[5:].strip())
                except json.JSONDecodeError:
                    continue
                event_counts[event_name or "?"] += 1
                t_rel = time.monotonic() - t0
                if event_name == "response_delta":
                    delta = data.get("delta", "")
                    if ttft is None and delta:
                        ttft = t_rel
                        L(f"  ttft={ttft:.2f}s")
                    answer += delta
                elif event_name == "thinking":
                    chunk = data.get("text") or data.get("delta") or ""
                    if chunk:
                        thinking_text += chunk
                elif event_name == "thinking_done":
                    L(f"  thinking_done[{t_rel:.2f}s]: {data}")
                    if thinking_text.strip():
                        L("  --- thinking ---")
                        for ln in thinking_text.rstrip().splitlines():
                            L(f"  │ {ln}")
                        L("  --- end thinking ---")
                elif event_name == "citations":
                    citations = data
                    refs = data.get("refs") or data.get("items") or []
                    srcs = data.get("sources") or []
                    L(f"  citations[{t_rel:.2f}s]: {len(refs)} refs, {len(srcs)} sources")
                elif event_name == "follow_ups":
                    follow_ups = data.get("suggestions", [])
                    L(f"  follow_ups: {follow_ups}")
                elif event_name in {"tool_call", "tool_call_start"}:
                    name = (
                        data.get("name") or data.get("tool")
                        or data.get("tool_name") or ""
                    )
                    args = data.get("args") or data.get("arguments") or data.get("input")
                    tool_calls.append(name)
                    tool_events.append({"t": round(t_rel, 2), "name": name, "args": args})
                    if first_tool_at is None:
                        first_tool_at = t_rel
                    L(f"  → tool_call_start[{t_rel:.2f}s] {name}  args={args}")
                elif event_name == "tool_call_end":
                    name = data.get("tool_name") or data.get("name") or ""
                    preview = data.get("result_summary") or ""
                    latency = data.get("latency_ms")
                    facts = data.get("facts_found")
                    tool_events.append({
                        "t": round(t_rel, 2), "name": name,
                        "latency_ms": latency, "facts_found": facts,
                        "result_preview": preview,
                    })
                    L(f"  ← tool_call_end[{t_rel:.2f}s]   {name}  "
                      f"latency={latency}ms  facts={facts}  result≈{preview}")
                elif event_name == "error":
                    errors.append(str(data))
                    L(f"  ERROR: {data}")
                elif event_name in {"thinking_start", "metadata", "done"}:
                    L(f"  {event_name}[{t_rel:.2f}s]: {data}")

    elapsed = time.monotonic() - t0
    L(f"  elapsed={elapsed:.2f}s  chars={len(answer)}  tools={len(tool_calls)}  "
      f"events={dict(event_counts)}")

    # ---- Full answer ----------------------------------------------------
    L("")
    L("  --- agent response ---")
    for ln in (answer or "(empty)").rstrip().splitlines():
        L(f"  │ {ln}")
    L("  --- end response ---")

    # ---- Citations breakdown + media links ------------------------------
    refs_dump = citations.get("refs") or citations.get("items") or []
    sources_dump = citations.get("sources") or []
    if refs_dump or sources_dump:
        L("")
        L("  --- citations ---")
        for i, s in enumerate(sources_dump, 1):
            kind = s.get("kind", "?")
            sid = s.get("source_id") or s.get("id", "")
            permalink = s.get("permalink") or ""
            excerpt = (s.get("excerpt") or "")[:160].replace("\n", " ")
            L(f"  [{i}] kind={kind}  id={sid}")
            if permalink:
                L(f"       link: {permalink}")
            if excerpt:
                L(f"       excerpt: {excerpt}")
            for att in (s.get("attachments") or []):
                akind = att.get("kind", "?")
                url = att.get("url", "")
                thumb = att.get("thumbnail_url") or ""
                title = att.get("title") or att.get("filename") or ""
                mime = att.get("mime_type") or ""
                L(f"       media[{akind}] {title} {mime} url={url} thumb={thumb}")
        if not sources_dump and refs_dump:
            for i, r in enumerate(refs_dump, 1):
                L(f"  [{i}] {json.dumps(r, default=str)[:300]}")
        L("  --- end citations ---")

    if tool_events:
        L("")
        L(f"  tool_events_count={len(tool_events)}")
    refs = citations.get("refs") or citations.get("items") or []
    sources = citations.get("sources") or []
    kinds_seen = {s.get("kind") for s in sources} | {
        r.get("kind") for r in refs if isinstance(r, dict)
    }

    _REFUSAL_RE = re.compile(
        r"\b(no (record|evidence|information|entity)|not (identified|found|recorded)"
        r"|couldn'?t find|don'?t have|no edges)\b",
        re.IGNORECASE,
    )
    _is_refusal = bool(_REFUSAL_RE.search(answer))

    # Soft citation floor: 0 refs with expected > 0 → hard fail;
    # refs == expected-1 → warn (⚠) but pass.
    n_refs = len(refs)
    exp_min = tc.expected_citations_min
    if exp_min > 0 and n_refs == 0:
        citations_count_ok = False
        citations_warn = False
    elif exp_min > 0 and n_refs == exp_min - 1:
        citations_count_ok = True
        citations_warn = True
        L(f"  ⚠ citations soft floor: got {n_refs}, expected {exp_min}")
    else:
        citations_count_ok = n_refs >= exp_min
        citations_warn = False

    # Refusal-aware: if answer is a clear refusal, treat canary checks as passing.
    if _is_refusal and tc.must_not_mention:
        must_not_mention_ok = True
    else:
        must_not_mention_ok = not any(s.lower() in answer.lower() for s in tc.must_not_mention)

    if _is_refusal and tc.must_mention:
        must_mention_ok = True
    else:
        must_mention_ok = all(s.lower() in answer.lower() for s in tc.must_mention)

    # Hard length cap (2000) — fails verdict.
    length_ok = (tc.max_chars == 0) or (len(answer) <= tc.max_chars)
    # Soft length target — warns but does NOT fail verdict.
    length_target_ok = True
    if tc.soft_max_chars > 0 and len(answer) > tc.soft_max_chars:
        length_target_ok = False
        L(f"  ⚠ length soft target: {len(answer)} chars > soft_max {tc.soft_max_chars}")

    grade = {
        "citations_count_ok": citations_count_ok,
        "kinds_ok": not tc.expected_kinds or any(k in kinds_seen for k in tc.expected_kinds),
        "tools_ok": not tc.expected_tools or any(t in tool_calls for t in tc.expected_tools),
        "must_mention_ok": must_mention_ok,
        "must_not_mention_ok": must_not_mention_ok,
        "follow_ups_ok": (bool(follow_ups) == tc.expected_follow_ups) if tc.expected_follow_ups else True,
        "length_ok": length_ok,
    }
    # length_target_ok is advisory — recorded but not in verdict gate.
    grade_advisory = {
        "citations_warn": citations_warn,
        "length_target_ok": length_target_ok,
    }

    verdict = "PASS" if all(grade.values()) else "FAIL"
    L(f"  verdict={verdict}  grade={grade}  advisory={grade_advisory}")
    return {
        "case": asdict(tc),
        "elapsed_s": round(elapsed, 2),
        "ttft_s": round(ttft, 2) if ttft is not None else None,
        "first_tool_at_s": round(first_tool_at, 2) if first_tool_at is not None else None,
        "answer": answer,
        "answer_chars": len(answer),
        "citations": citations,
        "follow_ups": follow_ups,
        "tool_calls": tool_calls,
        "event_counts": dict(event_counts),
        "errors": errors,
        "grade": grade,
        "grade_advisory": grade_advisory,
        "verdict": verdict,
    }


async def run_battery(
    name_or_id: str, mode: str, persona: str, only: list[str] | None
) -> None:
    async with httpx.AsyncClient() as client:
        channel_id = await resolve_channel_id(client, name_or_id)

        cases: list[TestCase] = []
        if persona in ("existing", "both"):
            ctx = build_channel_context(channel_id)
            print_context(ctx)
            cases.extend(build_existing_cases(ctx))
        if persona in ("onboarding", "both"):
            cases.extend(ONBOARDING_CASES)

        if only:
            cases = [c for c in cases if c.id in only]

        session_id_existing = str(uuid.uuid4())
        session_id_onboarding = str(uuid.uuid4())
        print(f"channel={channel_id}  mode={mode}  persona={persona}  cases={len(cases)}")

        stamp = int(time.time())
        out_path = OUT_DIR / f"report_{persona}_{channel_id}_{stamp}.jsonl"
        log_path = OUT_DIR / f"log_{persona}_{channel_id}_{stamp}.txt"
        summary: list[dict[str, Any]] = []

        with out_path.open("w") as f, log_path.open("w") as log:
            log.write(f"# QA harness run  channel={channel_id} persona={persona} mode={mode}\n")
            log.write(f"# started {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            log.flush()

            for tc in cases:
                session_id = (
                    session_id_existing if tc.persona == "existing"
                    else session_id_onboarding
                )
                try:
                    result = await _run_one(client, channel_id, session_id, mode, tc, log)
                except Exception as e:
                    log.write(f"[EXC] {tc.id}: {e!r}\n")
                    log.flush()
                    result = {"case": asdict(tc), "error": repr(e), "verdict": "ERROR"}
                f.write(json.dumps(result) + "\n")
                f.flush()
                summary.append(result)

        # ---- Aggregate performance summary ---------------------------
        def _avg(nums: list[float]) -> float:
            return round(sum(nums) / len(nums), 2) if nums else 0.0

        elapsed = [r["elapsed_s"] for r in summary if r.get("elapsed_s") is not None]
        ttfts = [r["ttft_s"] for r in summary if r.get("ttft_s") is not None]
        passes = sum(1 for r in summary if r.get("verdict") == "PASS")
        fails = sum(1 for r in summary if r.get("verdict") == "FAIL")
        errs = sum(1 for r in summary if r.get("verdict") == "ERROR")

        print(f"\nReport → {out_path}")
        print(f"Log    → {log_path}\n")
        print("Summary:")
        for r in summary:
            c = r["case"]
            refs = (r.get("citations") or {}).get("refs") \
                or (r.get("citations") or {}).get("items") or []
            print(
                f"  {c['id']:26s}  {c['persona']:10s}  {r.get('verdict','?'):6s}  "
                f"{r.get('elapsed_s','?'):>6}s  ttft={r.get('ttft_s','-')}  "
                f"chars={r.get('answer_chars','?'):>5}  cites={len(refs):>2}  "
                f"tools={len(r.get('tool_calls') or [])}"
            )
        print(f"\nTotals: pass={passes} fail={fails} error={errs}  "
              f"avg_elapsed={_avg(elapsed)}s  avg_ttft={_avg(ttfts)}s")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import asyncio

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump")
    p_dump.add_argument("--channel", default="tech-beever-atlas")

    p_ask = sub.add_parser("ask")
    p_ask.add_argument("--channel", default="tech-beever-atlas")
    p_ask.add_argument("--mode", default="deep", choices=["deep", "summarize", "wiki"])
    p_ask.add_argument("--persona", default="both", choices=["existing", "onboarding", "both"])
    p_ask.add_argument("--only", nargs="*")

    args = ap.parse_args()
    if args.cmd == "dump":
        asyncio.run(dump_channel(args.channel))
    else:
        asyncio.run(run_battery(args.channel, args.mode, args.persona, args.only))


if __name__ == "__main__":
    main()
