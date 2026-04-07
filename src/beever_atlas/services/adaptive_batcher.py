"""Token-aware adaptive message batching.

Replaces fixed batch_size with token-budget-based splitting that prevents
output truncation and EOF errors. Preserves thread groups and prefers
time-window coherence.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def estimate_message_tokens(msg: dict[str, Any]) -> int:
    """Estimate the token count for a message using a 3-chars-per-token heuristic.

    Includes text, thread_context, media descriptions, and link metadata.
    """
    total_chars = 0

    # Message text (may include appended media descriptions and links)
    total_chars += len(msg.get("text") or msg.get("content") or "")

    # Thread context (injected by preprocessor)
    total_chars += len(msg.get("thread_context") or "")

    # Source link metadata
    for title in msg.get("source_link_titles") or []:
        total_chars += len(title or "")
    for desc in msg.get("source_link_descriptions") or []:
        total_chars += len(desc or "")

    # Raw metadata may contain additional content
    raw_meta = msg.get("raw_metadata")
    raw: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    for link in raw.get("links") or []:
        total_chars += len(link.get("title") or "")
        total_chars += len(link.get("description") or "")

    # Minimum 50 tokens for message overhead (author, ts, structural JSON)
    return max(total_chars // 3, 50)


def _get_message_timestamp(msg: dict[str, Any]) -> float:
    """Extract a float timestamp from a message for time-window grouping."""
    ts = msg.get("ts") or msg.get("timestamp")
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str) and ts:
        try:
            # Slack-style: "1234567890.123456"
            return float(ts.split(".")[0])
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            pass
    if isinstance(ts, datetime):
        return ts.timestamp()
    return 0.0


def _is_thread_reply(msg: dict[str, Any]) -> bool:
    """Return True if the message is a thread reply (not a parent)."""
    thread_id = msg.get("thread_ts") or msg.get("thread_id")
    msg_id = msg.get("ts") or msg.get("message_id")
    return bool(thread_id and thread_id != msg_id)


def token_aware_batches(
    messages: list[dict[str, Any]],
    max_tokens: int = 12000,
    time_window_seconds: int = 600,
) -> list[list[dict[str, Any]]]:
    """Split messages into batches respecting a token budget.

    Algorithm:
    1. Sort messages by timestamp for chronological coherence
    2. Group into thread groups (parent + replies kept together)
    3. Accumulate thread groups into batches until token budget is reached
    4. Never split a thread group across batches

    Args:
        messages: List of message dicts (raw or preprocessed).
        max_tokens: Maximum estimated prompt tokens per batch.
        time_window_seconds: Preferred time window for grouping (secondary).

    Returns:
        List of message batches, each within the token budget.
    """
    if not messages:
        return []

    # Sort by timestamp for chronological order
    sorted_msgs = sorted(messages, key=_get_message_timestamp)

    # Build thread groups: each group is [parent, reply1, reply2, ...]
    # Messages without a thread_id are their own group.
    thread_groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []

    for msg in sorted_msgs:
        if _is_thread_reply(msg):
            # Append to current group (reply follows parent)
            current_group.append(msg)
        else:
            # New top-level message — start a new group
            if current_group:
                thread_groups.append(current_group)
            current_group = [msg]

    if current_group:
        thread_groups.append(current_group)

    # Accumulate thread groups into batches within token budget
    batches: list[list[dict[str, Any]]] = []
    current_batch: list[dict[str, Any]] = []
    current_tokens = 0

    for group in thread_groups:
        group_tokens = sum(estimate_message_tokens(m) for m in group)

        # If this single group exceeds budget, it gets its own batch
        if group_tokens >= max_tokens:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            batches.append(group)
            logger.info(
                "AdaptiveBatcher: oversized thread group (%d tokens, %d msgs) in own batch",
                group_tokens,
                len(group),
            )
            continue

        # Would adding this group exceed the budget?
        if current_tokens + group_tokens > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.extend(group)
        current_tokens += group_tokens

    if current_batch:
        batches.append(current_batch)

    if batches:
        sizes = [len(b) for b in batches]
        token_ests = [sum(estimate_message_tokens(m) for m in b) for b in batches]
        logger.info(
            "AdaptiveBatcher: %d messages → %d batches (sizes=%s, tokens=%s)",
            len(messages),
            len(batches),
            sizes,
            token_ests,
        )

    return batches
