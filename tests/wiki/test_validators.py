"""Unit tests for wiki content validators (Phase 1, task 2.2)."""

from __future__ import annotations

from beever_atlas.wiki.validators import (
    banned_phrases,
    combine,
    mermaid_balanced,
    min_length,
    required_headings,
)


def test_min_length_pass():
    ok, reason = min_length(10)("hello world 123")
    assert ok and reason == ""


def test_min_length_fail():
    ok, reason = min_length(50)("short")
    assert not ok
    assert "too short" in reason.lower()


def test_mermaid_balanced_pass():
    content = "text\n```mermaid\ngraph TD\nA-->B\n```\nmore text"
    ok, reason = mermaid_balanced(content)
    assert ok, reason


def test_mermaid_balanced_fail_unclosed():
    content = "text\n```mermaid\ngraph TD\nA-->B\nmore text no close"
    ok, reason = mermaid_balanced(content)
    assert not ok
    assert "mermaid" in reason.lower()


def test_mermaid_balanced_multiple_blocks():
    content = "```mermaid\nA\n```\n\n```mermaid\nB\n```"
    assert mermaid_balanced(content)[0]


def test_required_headings_pass():
    v = required_headings(("Overview", "Key Facts"))
    content = "## Overview\nhi\n## Key Facts\n| a | b |"
    ok, _ = v(content)
    assert ok


def test_required_headings_missing():
    v = required_headings(("Overview",))
    content = "## Summary\nhi"
    ok, reason = v(content)
    assert not ok
    assert "Overview" in reason


def test_banned_phrases_under_threshold():
    content = "This topic is crucial for the project."
    ok, _ = banned_phrases(content)
    assert ok


def test_banned_phrases_triggers():
    content = "This is crucial for testing. It is important to note under discussion."
    ok, reason = banned_phrases(content)
    assert not ok
    assert "filler" in reason.lower()


def test_combine_first_failure_wins():
    v = combine(min_length(100), mermaid_balanced)
    ok, reason = v("short")
    assert not ok
    assert "short" in reason.lower()
