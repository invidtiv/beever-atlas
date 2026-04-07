"""Live dry-run — fetch real Slack messages via Chat SDK bridge and test ingestion.

Connects to the running bot service bridge, fetches real messages from a Slack
channel, then runs them through the ingestion pipeline stages with detailed
performance logging. No data is persisted (dry-run mode).

Prerequisites:
  - Bot service running (npm run dev in bot/)
  - Slack bot connected to a workspace
  - .env configured with BRIDGE_URL, GOOGLE_API_KEY, JINA_API_KEY

Usage:
    # List available channels:
    python scripts/dry_run_live.py --list-channels

    # Run on a specific channel (default: first 20 messages):
    python scripts/dry_run_live.py --channel C0AMY9QSPB2

    # Specify message count:
    python scripts/dry_run_live.py --channel C0AMY9QSPB2 --limit 50

    # Include thread replies:
    python scripts/dry_run_live.py --channel C0AMY9QSPB2 --threads

    # Preprocessor only (no LLM calls):
    python scripts/dry_run_live.py --channel C0AMY9QSPB2 --preprocess-only

    # Single stage:
    python scripts/dry_run_live.py --channel C0AMY9QSPB2 --stage facts

    # Verbose JSON output:
    python scripts/dry_run_live.py --channel C0AMY9QSPB2 --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import logging
import os
import time
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Suppress noisy warnings before any imports trigger them
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Quiet noisy loggers
for _logger_name in (
    "google", "google.adk", "google.genai", "httpx", "httpcore",
    "aiohttp", "grpc", "urllib3",
    "beever_atlas.services.coreference_resolver",
    "beever_atlas.services.media_processor",
    "beever_atlas.services.media_extractors",
    "beever_atlas.adapters.bridge",
):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)
logging.getLogger("google.adk.runners").setLevel(logging.ERROR)


# ── Formatting ────────────────────────────────────────────────────────

class _C:
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


def _warn(msg: str) -> None:
    print(f"  {_C.YELLOW}!{_C.RESET} {msg}")


def _info(msg: str) -> None:
    print(f"  {_C.DIM}│{_C.RESET} {msg}")


def _metric(label: str, value: Any, unit: str = "") -> None:
    val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
    print(f"  {_C.DIM}│{_C.RESET}  {label:<30} {_C.BOLD}{val_str}{_C.RESET} {unit}")


# ── Bridge helpers ────────────────────────────────────────────────────

async def create_adapter():
    """Create a ChatBridgeAdapter connected to the running bot service."""
    from beever_atlas.adapters.bridge import ChatBridgeAdapter
    from beever_atlas.infra.config import get_settings

    settings = get_settings()
    adapter = ChatBridgeAdapter(
        bridge_url=settings.bridge_url,
        api_key=settings.bridge_api_key,
    )
    return adapter, settings


async def list_channels() -> list[dict[str, Any]]:
    """List all channels available via the bridge."""
    adapter, _ = await create_adapter()
    channels = await adapter.list_channels()
    return [
        {
            "id": ch.channel_id,
            "name": ch.name,
            "platform": ch.platform,
            "member_count": ch.member_count,
        }
        for ch in channels
    ]


async def fetch_messages(
    channel_id: str,
    limit: int = 20,
    include_threads: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch real messages from a Slack channel via the bridge.

    Returns (messages_as_dicts, fetch_stats).
    """
    adapter, _ = await create_adapter()

    # Get channel info
    channel_info = await adapter.get_channel_info(channel_id)

    # Fetch messages (oldest first for natural reading order)
    t0 = time.monotonic()
    messages = await adapter.fetch_history(channel_id, limit=limit, order="asc")
    fetch_time = time.monotonic() - t0

    parent_count = len(messages)
    thread_replies: list[Any] = []

    # Optionally fetch thread replies
    if include_threads:
        thread_parents = [m for m in messages if m.reply_count and m.reply_count > 0]
        if thread_parents:
            sem = asyncio.Semaphore(3)

            async def _fetch_thread(msg: Any) -> list[Any]:
                async with sem:
                    try:
                        replies = await adapter.fetch_thread(channel_id, msg.message_id)
                        # Exclude parent (Slack includes it as first reply)
                        return [r for r in replies if r.message_id != msg.message_id]
                    except Exception as e:
                        _warn(f"Failed to fetch thread {msg.message_id}: {e}")
                        return []

            results = await asyncio.gather(*[_fetch_thread(m) for m in thread_parents])
            for replies in results:
                thread_replies.extend(replies)

    # Convert NormalizedMessage objects to dicts for the pipeline
    all_msgs = list(messages) + thread_replies

    def _to_dict(m: Any) -> dict[str, Any]:
        return {
            "content": m.content,
            "text": m.content,
            "author": m.author,
            "author_name": m.author_name,
            "author_image": getattr(m, "author_image", ""),
            "platform": m.platform,
            "channel_id": m.channel_id,
            "channel_name": m.channel_name or channel_info.name,
            "message_id": m.message_id,
            "ts": m.message_id,
            "timestamp": m.timestamp.isoformat(),
            "thread_id": m.thread_id,
            "thread_ts": m.thread_id,
            "attachments": m.attachments or [],
            "reactions": m.reactions or [],
            "reply_count": m.reply_count or 0,
            "raw_metadata": m.raw_metadata or {},
            "is_bot": m.raw_metadata.get("is_bot", False) if m.raw_metadata else False,
        }

    messages_dicts = [_to_dict(m) for m in all_msgs]

    stats = {
        "channel_name": channel_info.name,
        "channel_id": channel_id,
        "platform": channel_info.platform,
        "parent_messages": parent_count,
        "thread_replies": len(thread_replies),
        "total_messages": len(messages_dicts),
        "fetch_time": fetch_time,
    }

    return messages_dicts, stats


# ── Pipeline stage runner ─────────────────────────────────────────────

async def run_stage(
    stage_name: str,
    messages_or_input: list[dict[str, Any]],
    *,
    channel_id: str,
    channel_name: str,
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
            "sync_job_id": "dry-run-live",
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
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        async for _ in runner.run_async(
            user_id="dev", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=f"run {stage_name}")]),
        ):
            event_count += 1
    elapsed = time.monotonic() - t0

    final = await session_service.get_session(app_name="ingestion", user_id="dev", session_id=session.id)
    output = (final.state.get(output_key) or []) if final else []

    return {"output": output, "elapsed": elapsed, "events": event_count, "output_key": output_key}


# ── Reporting ─────────────────────────────────────────────────────────

def report_fetch(stats: dict[str, Any], messages: list[dict[str, Any]]) -> None:
    """Print fetch results."""
    _metric("Channel", f"{stats['channel_name']} ({stats['channel_id']})")
    _metric("Platform", stats["platform"])
    _metric("Parent messages", stats["parent_messages"])
    _metric("Thread replies", stats["thread_replies"])
    _metric("Total messages", stats["total_messages"])
    _metric("Fetch time", stats["fetch_time"], "s")
    print()

    # Message preview
    _subheader("Messages Fetched")
    for i, msg in enumerate(messages[:30]):  # Cap preview at 30
        author = msg.get("author_name") or msg.get("author") or "?"
        text = (msg.get("text") or "")[:70]
        ts = msg.get("timestamp", "")[:19]
        platform = msg.get("platform", "?")
        is_bot = msg.get("is_bot", False)
        is_reply = bool(msg.get("thread_id"))
        attachments = msg.get("attachments", [])

        badges = []
        if is_bot:
            badges.append(f"{_C.DIM}BOT{_C.RESET}")
        if is_reply:
            badges.append(f"{_C.BLUE}REPLY{_C.RESET}")
        if attachments:
            types_str = ", ".join(a.get("type", "?") for a in attachments[:3])
            badges.append(f"{_C.YELLOW}{types_str}{_C.RESET}")
        if msg.get("reply_count", 0) > 0:
            badges.append(f"{_C.CYAN}💬{msg['reply_count']}{_C.RESET}")

        badge_str = f" [{', '.join(badges)}]" if badges else ""
        indent = "  ↳ " if is_reply else ""
        ellipsis = "…" if len(msg.get("text", "")) > 70 else ""
        _info(f"{indent}{_C.DIM}{ts}{_C.RESET} {author}: {text}{ellipsis}{badge_str}")

    if len(messages) > 30:
        _info(f"... and {len(messages) - 30} more messages")

    # Content analysis
    print()
    _subheader("Content Analysis")
    bots = sum(1 for m in messages if m.get("is_bot"))
    threads = sum(1 for m in messages if m.get("thread_id"))
    with_attachments = sum(1 for m in messages if m.get("attachments"))
    with_reactions = sum(1 for m in messages if m.get("reactions"))
    with_links = sum(1 for m in messages if "http" in (m.get("text") or ""))
    platforms = set(m.get("platform", "?") for m in messages)
    authors = set(m.get("author") for m in messages)
    avg_len = sum(len(m.get("text") or "") for m in messages) / max(len(messages), 1)

    _metric("Unique authors", len(authors))
    _metric("Platforms", ", ".join(sorted(platforms)))
    _metric("Bot messages", bots)
    _metric("Thread replies", threads)
    _metric("With attachments", with_attachments)
    _metric("With reactions", with_reactions)
    _metric("With links", with_links)
    _metric("Avg message length", f"{avg_len:.0f}", "chars")

    # Attachment type breakdown
    if with_attachments:
        att_types: dict[str, int] = {}
        for m in messages:
            for a in m.get("attachments", []):
                t = a.get("type", "unknown")
                att_types[t] = att_types.get(t, 0) + 1
        _metric("Attachment types", json.dumps(att_types))


def _extract_media_sections(text: str) -> dict[str, str]:
    """Parse media sections from preprocessed message text.

    Detects: [Attachment:...], [Document text:...], [Image description:...],
    [Video transcript:...], [Audio transcript:...], [Keyframe descriptions:...]
    """
    import re
    sections: dict[str, str] = {}
    # Find attachment metadata
    att_match = re.search(r'\[Attachment:\s*(.+?)(?:\])', text)
    if att_match:
        sections["attachment"] = att_match.group(1).strip()

    # Find document text (PDF)
    doc_match = re.search(r'\[Document text:\s*(.*?)(?:\]$|\Z)', text, re.DOTALL)
    if doc_match:
        sections["document_text"] = doc_match.group(1).strip()

    # Find image description
    img_match = re.search(r'\[Image description:\s*(.*?)(?:\]$|\Z)', text, re.DOTALL)
    if img_match:
        sections["image_description"] = img_match.group(1).strip()

    # Find video transcript
    vid_match = re.search(r'\[Video transcript:\s*(.*?)(?:\]$|\Z)', text, re.DOTALL)
    if vid_match:
        sections["video_transcript"] = vid_match.group(1).strip()

    # Find video transcript (English translation)
    vid_en_match = re.search(r'\[Video transcript \(English\):\s*(.*?)(?:\]$|\Z)', text, re.DOTALL)
    if vid_en_match:
        sections["video_transcript_en"] = vid_en_match.group(1).strip()

    # Find video visual description
    vid_vis_match = re.search(r'\[Video visual description:\s*(.*?)(?:\]$|\Z)', text, re.DOTALL)
    if vid_vis_match:
        sections["video_visual"] = vid_vis_match.group(1).strip()

    # Find audio transcript
    aud_match = re.search(r'\[Audio transcript:\s*(.*?)(?:\]$|\Z)', text, re.DOTALL)
    if aud_match:
        sections["audio_transcript"] = aud_match.group(1).strip()

    # Find audio transcript (English translation)
    aud_en_match = re.search(r'\[Audio transcript \(English\):\s*(.*?)(?:\]$|\Z)', text, re.DOTALL)
    if aud_en_match:
        sections["audio_transcript_en"] = aud_en_match.group(1).strip()

    return sections


def _chunk_text(text: str, max_chars: int = 300) -> list[str]:
    """Split text into readable chunks at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        # Find last sentence boundary within limit
        cut = remaining[:max_chars].rfind(". ")
        if cut < max_chars // 3:
            cut = remaining[:max_chars].rfind(" ")
        if cut < max_chars // 3:
            cut = max_chars
        chunks.append(remaining[: cut + 1].strip())
        remaining = remaining[cut + 1 :].strip()
    return chunks


def report_preprocessor(messages_in: list, result: dict, verbose: bool) -> dict[str, Any]:
    """Print preprocessor diagnostics with detailed media extraction."""
    output = result["output"]

    _metric("Input messages", len(messages_in))
    _metric("Output messages", len(output))
    _metric("Filtered", len(messages_in) - len(output))
    _metric("Time", result["elapsed"], "s")
    _metric("Throughput", len(messages_in) / max(result["elapsed"], 0.01), "msg/s")
    print()

    stats = {
        "coref": 0, "thread_ctx": 0, "links": 0,
        "multimodal": 0, "platforms": set(), "bot_filtered": len(messages_in) - len(output),
    }

    _subheader("Processed Messages")
    for msg in output[:25]:
        author = msg.get("username") or msg.get("author_name") or "?"
        platform = msg.get("platform", "?")
        full_text = msg.get("text") or ""
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

        badge_str = f" [{', '.join(badges)}]" if badges else ""
        # Show first line of original message content
        first_line = full_text.split("\n")[0][:75]
        ellipsis = "…" if len(full_text.split("\n")[0]) > 75 else ""
        _info(f"[{platform}] {author}: {first_line}{ellipsis}{badge_str}")
        _info(f"  {_C.DIM}text length: {len(full_text)} chars | modality: {msg.get('modality', 'text')}{_C.RESET}")

        # ── Media extraction details ──────────────────────────────────
        sections = _extract_media_sections(full_text)

        if sections.get("attachment"):
            _info(f"  {_C.YELLOW}📎 {sections['attachment']}{_C.RESET}")

        if sections.get("document_text"):
            doc_text = sections["document_text"]
            _info(f"  {_C.GREEN}📄 PDF Content Extracted ({len(doc_text)} chars):{_C.RESET}")
            chunks = _chunk_text(doc_text, 120)
            for chunk in chunks[:8]:  # Show up to 8 chunks
                _info(f"     {_C.DIM}{chunk}{_C.RESET}")
            if len(chunks) > 8:
                _info(f"     {_C.DIM}... ({len(chunks) - 8} more chunks){_C.RESET}")

        if sections.get("image_description"):
            img_desc = sections["image_description"]
            _info(f"  {_C.CYAN}🖼  Image Vision Description ({len(img_desc)} chars):{_C.RESET}")
            chunks = _chunk_text(img_desc, 120)
            for chunk in chunks[:6]:
                _info(f"     {_C.DIM}{chunk}{_C.RESET}")
            if len(chunks) > 6:
                _info(f"     {_C.DIM}... ({len(chunks) - 6} more lines){_C.RESET}")

        if sections.get("video_transcript"):
            vid_text = sections["video_transcript"]
            _info(f"  {_C.MAGENTA}🎬 Video Transcript ({len(vid_text)} chars):{_C.RESET}")
            chunks = _chunk_text(vid_text, 120)
            for chunk in chunks[:8]:
                _info(f"     {_C.DIM}{chunk}{_C.RESET}")
            if len(chunks) > 8:
                _info(f"     {_C.DIM}... ({len(chunks) - 8} more chunks){_C.RESET}")

        if sections.get("video_transcript_en"):
            en_text = sections["video_transcript_en"]
            _info(f"  {_C.MAGENTA}🎬 Video Transcript (English) ({len(en_text)} chars):{_C.RESET}")
            chunks = _chunk_text(en_text, 120)
            for chunk in chunks[:6]:
                _info(f"     {_C.DIM}{chunk}{_C.RESET}")
            if len(chunks) > 6:
                _info(f"     {_C.DIM}... ({len(chunks) - 6} more chunks){_C.RESET}")

        if sections.get("video_visual"):
            vis_text = sections["video_visual"]
            _info(f"  {_C.MAGENTA}🎞  Video Visual Description ({len(vis_text)} chars):{_C.RESET}")
            chunks = _chunk_text(vis_text, 120)
            for chunk in chunks[:6]:
                _info(f"     {_C.DIM}{chunk}{_C.RESET}")
            if len(chunks) > 6:
                _info(f"     {_C.DIM}... ({len(chunks) - 6} more chunks){_C.RESET}")

        if sections.get("audio_transcript"):
            aud_text = sections["audio_transcript"]
            _info(f"  {_C.BLUE}🎵 Audio Transcript ({len(aud_text)} chars):{_C.RESET}")
            chunks = _chunk_text(aud_text, 120)
            for chunk in chunks[:8]:
                _info(f"     {_C.DIM}{chunk}{_C.RESET}")
            if len(chunks) > 8:
                _info(f"     {_C.DIM}... ({len(chunks) - 8} more chunks){_C.RESET}")

        if sections.get("audio_transcript_en"):
            en_text = sections["audio_transcript_en"]
            _info(f"  {_C.BLUE}🎵 Audio Transcript (English) ({len(en_text)} chars):{_C.RESET}")
            chunks = _chunk_text(en_text, 120)
            for chunk in chunks[:6]:
                _info(f"     {_C.DIM}{chunk}{_C.RESET}")
            if len(chunks) > 6:
                _info(f"     {_C.DIM}... ({len(chunks) - 6} more chunks){_C.RESET}")

        # ── Link details ──────────────────────────────────────────────
        link_urls = msg.get("source_link_urls", [])
        link_titles = msg.get("source_link_titles", [])
        if link_urls:
            for j, url in enumerate(link_urls):
                title = link_titles[j] if j < len(link_titles) and link_titles[j] else ""
                title_str = f" — {title}" if title else ""
                _info(f"  {_C.CYAN}🔗 {url}{title_str}{_C.RESET}")

        # ── Thread context ────────────────────────────────────────────
        if msg.get("thread_context"):
            _info(f"  {_C.BLUE}🧵 Thread context: {msg['thread_context'][:120]}{_C.RESET}")

        print()  # Blank line between messages

    if len(output) > 25:
        _info(f"... and {len(output) - 25} more")

    _subheader("Feature Summary")
    _metric("Coreference resolved", stats["coref"], "messages")
    _metric("Thread context added", stats["thread_ctx"], "messages")
    _metric("Links extracted", stats["links"], "messages")
    _metric("Multimodal detected", stats["multimodal"], "messages")
    _metric("Platforms", ", ".join(sorted(stats["platforms"])))
    _metric("Bot messages filtered", stats["bot_filtered"])

    if verbose:
        print(f"\n{_C.DIM}  Raw preprocessor output:{_C.RESET}")
        print(json.dumps(output, indent=2, default=str))

    return stats


def report_llm_input(preprocessed: list[dict[str, Any]]) -> None:
    """Show the combined input that will be passed to fact/entity extraction LLMs."""
    _header("LLM Input — What the Extraction Models See")

    total_chars = 0
    for i, msg in enumerate(preprocessed, 1):
        author = msg.get("username") or msg.get("author_name") or "?"
        text = msg.get("text") or ""
        ts = msg.get("timestamp", "")[:19]
        total_chars += len(text)

        print(f"\n  {_C.BOLD}Message {i}/{len(preprocessed)}{_C.RESET}"
              f"  {_C.DIM}{ts} by {author}{_C.RESET}")
        print(f"  {_C.DIM}{'─' * 60}{_C.RESET}")

        # Split by sections and display with formatting
        lines = text.split("\n")
        in_section = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("[Attachment:"):
                in_section = "attachment"
                print(f"  {_C.YELLOW}  {stripped}{_C.RESET}")
            elif stripped.startswith("[Document text:"):
                in_section = "document"
                print(f"  {_C.GREEN}  {stripped[:120]}{'…' if len(stripped) > 120 else ''}{_C.RESET}")
            elif stripped.startswith("[Image description:"):
                in_section = "image"
                print(f"  {_C.CYAN}  {stripped[:120]}{'…' if len(stripped) > 120 else ''}{_C.RESET}")
            elif stripped.startswith("[Video transcript"):
                in_section = "video"
                print(f"  {_C.MAGENTA}  {stripped[:120]}{'…' if len(stripped) > 120 else ''}{_C.RESET}")
            elif stripped.startswith("[Video visual description:"):
                in_section = "video_visual"
                print(f"  {_C.MAGENTA}  {stripped[:120]}{'…' if len(stripped) > 120 else ''}{_C.RESET}")
            elif stripped.startswith("[Audio transcript"):
                in_section = "audio"
                print(f"  {_C.BLUE}  {stripped[:120]}{'…' if len(stripped) > 120 else ''}{_C.RESET}")
            elif in_section in ("document", "image", "video", "video_visual", "audio"):
                print(f"  {_C.DIM}  {stripped[:120]}{'…' if len(stripped) > 120 else ''}{_C.RESET}")
            else:
                in_section = None
                print(f"    {stripped[:120]}{'…' if len(stripped) > 120 else ''}")

    print(f"\n  {_C.BOLD}Total LLM input: {len(preprocessed)} messages, {total_chars:,} chars{_C.RESET}")
    if total_chars > 10000:
        _warn(f"Large input ({total_chars:,} chars) — may increase LLM latency and cost")


def report_extraction(stage_name: str, result: dict, verbose: bool) -> dict[str, Any]:
    """Print fact or entity extraction diagnostics."""
    raw = result["output"]
    stats: dict[str, Any] = {"elapsed": result["elapsed"]}

    if stage_name == "facts":
        facts = raw.get("facts") if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        if not isinstance(facts, list):
            facts = []
        stats["count"] = len(facts)
        stats["facts"] = facts

        _metric("Facts extracted", len(facts))
        _metric("Time", result["elapsed"], "s")
        if facts:
            _metric("Throughput", len(facts) / max(result["elapsed"], 0.01), "facts/s")
        print()

        if facts:
            _subheader("Extracted Facts")
            for f in facts[:20]:
                score = f.get("quality_score", 0)
                imp = f.get("importance", "?")
                text = f.get("memory_text", "")[:80]
                tags = f.get("entity_tags", [])

                if score >= 0.7:
                    icon = f"{_C.GREEN}+{_C.RESET}"
                elif score >= 0.4:
                    icon = f"{_C.YELLOW}~{_C.RESET}"
                else:
                    icon = f"{_C.RED}-{_C.RESET}"

                _info(f"[{icon}] [{score:.2f}|{imp}] {text}")
                if tags:
                    _info(f"      entities: {', '.join(tags)}")

            if len(facts) > 20:
                _info(f"... and {len(facts) - 20} more facts")

            print()
            _subheader("Fact Quality Distribution")
            scores = [f.get("quality_score", 0) for f in facts]
            high = sum(1 for s in scores if s >= 0.7)
            med = sum(1 for s in scores if 0.4 <= s < 0.7)
            low = sum(1 for s in scores if s < 0.4)
            _metric("High quality (≥0.7)", high)
            _metric("Medium (0.4–0.7)", med)
            _metric("Low (<0.4)", low)
            _metric("Average score", sum(scores) / len(scores))

            imp_dist: dict[str, int] = {}
            for f in facts:
                i = f.get("importance", "unknown")
                imp_dist[i] = imp_dist.get(i, 0) + 1
            _metric("Importance", json.dumps(imp_dist))

    elif stage_name == "entities":
        entities = raw.get("entities") if isinstance(raw, dict) else []
        relationships = raw.get("relationships") if isinstance(raw, dict) else []
        if not isinstance(entities, list):
            entities = []
        if not isinstance(relationships, list):
            relationships = []

        stats["entities"] = len(entities)
        stats["relationships"] = len(relationships)
        stats["entity_list"] = entities
        stats["relationship_list"] = relationships

        _metric("Entities", len(entities))
        _metric("Relationships", len(relationships))
        _metric("Time", result["elapsed"], "s")
        print()

        if entities:
            _subheader("Extracted Entities")
            type_dist: dict[str, int] = {}
            for e in entities[:20]:
                etype = e.get("type", "?")
                name = e.get("name", "?")
                aliases = e.get("aliases", [])
                type_dist[etype] = type_dist.get(etype, 0) + 1
                alias_str = f" {_C.DIM}(aka: {', '.join(aliases)}){_C.RESET}" if aliases else ""
                _info(f"[{etype}] {name}{alias_str}")

            if len(entities) > 20:
                _info(f"... and {len(entities) - 20} more entities")

            print()
            _subheader("Entity Type Distribution")
            for etype, count in sorted(type_dist.items()):
                _metric(etype, count)

        if relationships:
            print()
            _subheader("Extracted Relationships")
            for r in relationships[:15]:
                src = r.get("source", "?")
                tgt = r.get("target", "?")
                rtype = r.get("type", "?")
                conf = r.get("confidence", 0)
                _info(f"{src} ──[{rtype}]──▸ {tgt} {_C.DIM}(conf={conf:.1f}){_C.RESET}")

            if len(relationships) > 15:
                _info(f"... and {len(relationships) - 15} more relationships")

    if verbose:
        print(f"\n{_C.DIM}  Raw output:{_C.RESET}")
        print(json.dumps(raw, indent=2, default=str))

    return stats


# ── Main ──────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="Live dry-run ingestion test via Chat SDK bridge")
    parser.add_argument("--list-channels", action="store_true", help="List available channels and exit")
    parser.add_argument("--channel", "-c", help="Channel ID to test (e.g., C0AMY9QSPB2)")
    parser.add_argument("--limit", "-n", type=int, default=20, help="Number of messages to fetch (default: 20)")
    parser.add_argument("--threads", action="store_true", help="Include thread replies")
    parser.add_argument("--preprocess-only", action="store_true", help="Only run preprocessor (no LLM)")
    parser.add_argument("--stage", choices=["preprocessor", "facts", "entities"], help="Run single stage")
    parser.add_argument("--verbose", action="store_true", help="Print full JSON output")
    args = parser.parse_args()

    # ── List channels mode ────────────────────────────────────────────
    if args.list_channels:
        print(f"\n{_C.BOLD}Fetching channels from bridge...{_C.RESET}\n")
        try:
            channels = await list_channels()
        except Exception as e:
            _fail(f"Could not connect to bridge: {e}")
            _info("Make sure the bot service is running (npm run dev in bot/)")
            return

        if not channels:
            _warn("No channels found. Is the bot connected to Slack?")
            return

        print(f"  {'ID':<17} {'Name':<25} {'Platform':<10} Members")
        print(f"  {'─' * 17} {'─' * 25} {'─' * 10} {'─' * 7}")
        for ch in channels:
            members = ch.get("member_count") or "?"
            print(f"  {ch['id']:<17} {ch['name']:<25} {ch['platform']:<10} {members}")
        print(f"\n  {len(channels)} channels found")
        print(f"\n  {_C.DIM}Usage: python scripts/dry_run_live.py --channel <ID>{_C.RESET}\n")
        return

    if not args.channel:
        parser.error("--channel is required (use --list-channels to see available channels)")

    # ── Main pipeline run ─────────────────────────────────────────────
    print(f"\n{_C.BOLD}{'═' * 70}")
    print(f"  BEEVER ATLAS — LIVE DRY RUN")
    print(f"  Channel: {args.channel} | Limit: {args.limit} | Threads: {args.threads}")
    print(f"{'═' * 70}{_C.RESET}")

    timings: dict[str, float] = {}

    # ── Step 1: Fetch from Slack ──────────────────────────────────────
    _header("Step 1: Fetch Messages from Slack")
    try:
        messages, fetch_stats = await fetch_messages(
            args.channel, limit=args.limit, include_threads=args.threads,
        )
    except Exception as e:
        _fail(f"Could not fetch messages: {e}")
        _info("Make sure the bot service is running and the channel ID is correct.")
        return

    if not messages:
        _warn("No messages found in this channel.")
        return

    timings["fetch"] = fetch_stats["fetch_time"]
    report_fetch(fetch_stats, messages)

    channel_name = fetch_stats["channel_name"]

    # Initialize LLM if needed
    settings = None
    if not args.preprocess_only and args.stage != "preprocessor":
        from beever_atlas.infra.config import get_settings
        from beever_atlas.llm.provider import init_llm_provider
        settings = get_settings()
        init_llm_provider(settings)

    # ── Step 2: Preprocessor ──────────────────────────────────────────
    _header("Step 2: Preprocessor")
    prep_result = await run_stage(
        "preprocessor", messages,
        channel_id=args.channel, channel_name=channel_name,
    )
    timings["preprocessor"] = prep_result["elapsed"]
    preprocessed = prep_result["output"]
    prep_stats = report_preprocessor(messages, prep_result, args.verbose)

    # ── Step 2b: Show LLM Input ─────────────────────────────────────
    report_llm_input(preprocessed)

    if args.preprocess_only or args.stage == "preprocessor":
        _print_summary(timings, fetch_stats, prep_stats, None, None)
        return

    # ── Step 3: Fact Extraction ───────────────────────────────────────
    fact_stats = None
    if args.stage in (None, "facts"):
        _header("Step 3a: Fact Extraction (LLM)")
        fact_result = await run_stage(
            "facts", preprocessed,
            channel_id=args.channel, channel_name=channel_name, settings=settings,
        )
        timings["fact_extractor"] = fact_result["elapsed"]
        fact_stats = report_extraction("facts", fact_result, args.verbose)

    if args.stage == "facts":
        _print_summary(timings, fetch_stats, prep_stats, fact_stats, None)
        return

    # ── Step 4: Entity Extraction ─────────────────────────────────────
    entity_stats = None
    if args.stage in (None, "entities"):
        _header("Step 3b: Entity Extraction (LLM)")
        entity_result = await run_stage(
            "entities", preprocessed,
            channel_id=args.channel, channel_name=channel_name, settings=settings,
        )
        timings["entity_extractor"] = entity_result["elapsed"]
        entity_stats = report_extraction("entities", entity_result, args.verbose)

    if args.stage == "entities":
        _print_summary(timings, fetch_stats, prep_stats, None, entity_stats)
        return

    # ── Summary ───────────────────────────────────────────────────────
    _print_summary(timings, fetch_stats, prep_stats, fact_stats, entity_stats)

    # ── Save results ──────────────────────────────────────────────────
    output_dir = Path(".omc/cache")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "dry-run-live-result.json"
    output_file.write_text(json.dumps({
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "channel": fetch_stats,
        "timings": timings,
        "preprocessed_count": len(preprocessed),
        "facts": fact_stats.get("facts", []) if fact_stats else [],
        "entities": entity_stats.get("entity_list", []) if entity_stats else [],
        "relationships": entity_stats.get("relationship_list", []) if entity_stats else [],
    }, indent=2, default=str))
    _info(f"Results saved to {output_file}")
    print()


def _print_summary(
    timings: dict[str, float],
    fetch_stats: dict[str, Any],
    prep_stats: dict[str, Any],
    fact_stats: dict[str, Any] | None,
    entity_stats: dict[str, Any] | None,
) -> None:
    _header("Pipeline Summary")
    total_time = sum(timings.values())
    msg_count = fetch_stats["total_messages"]

    _metric("Channel", f"{fetch_stats['channel_name']} ({fetch_stats['channel_id']})")
    _metric("Messages fetched", msg_count)
    _metric("Messages preprocessed", msg_count - prep_stats.get("bot_filtered", 0))
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
    if total_time > 0 and msg_count > 0:
        _metric("Throughput", msg_count / total_time, "msg/s")
    print()


if __name__ == "__main__":
    asyncio.run(main())
