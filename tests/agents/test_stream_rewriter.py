"""Tests for Fix #7 / #12 / #13 in stream_rewriter.

Covers:
- `[External: user content]` is preserved through the rewriter (the
  tightened regex only strips the citation-registry src_<10hex> form).
- LiteralSrcStripper buffer never grows unboundedly under pathological
  input.
- The leftover-tag regex is gated by a `'[' in text` check so the
  common no-bracket chunk path skips the regex entirely.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from beever_atlas.agents.citations.registry import SourceRegistry
from beever_atlas.agents.query import stream_rewriter as sr_mod
from beever_atlas.agents.query.stream_rewriter import (
    LiteralSrcStripper,
    StreamRewriter,
    _LITERAL_STRIPPER_BUF_CAP,
)


@pytest.fixture
def registry():
    return SourceRegistry()


# ---------------------------------------------------------------------------
# Fix #7 — External: arm now matches only citation-registry ids.
# ---------------------------------------------------------------------------


def test_external_url_preserved(registry):
    rw = StreamRewriter(registry=registry)
    text = "See [External: https://example.com/docs] for more."
    out = rw.feed(text) + rw.flush()
    assert "[External: https://example.com/docs]" in out


def test_external_user_note_preserved(registry):
    rw = StreamRewriter(registry=registry)
    text = "Pasted [External: some casual user note] here."
    out = rw.feed(text) + rw.flush()
    assert "[External: some casual user note]" in out


def test_external_citation_literal_still_stripped(registry):
    rw = StreamRewriter(registry=registry)
    text = "Body [External: src_ab12cd34ef inline] continues."
    out = rw.feed(text) + rw.flush()
    assert "[External:" not in out
    assert "src_ab12cd34ef" not in out


def test_src_tool_name_literal_still_stripped(registry):
    """Regression: `[src:tool_name_response]` must still be stripped."""
    rw = StreamRewriter(registry=registry)
    text = "Answer [src:get_topic_overview_response] rest."
    out = rw.feed(text) + rw.flush()
    assert "[src:" not in out


# ---------------------------------------------------------------------------
# Fix #12 — LiteralSrcStripper buffer is bounded.
# ---------------------------------------------------------------------------


def test_literal_stripper_buffer_never_exceeds_cap():
    """Feed 10 chunks of 200 chars each starting with '[' and no ']'.

    Without the cap the buffer would grow to 2000 chars; with the cap it
    is drained long before that.
    """
    stripper = LiteralSrcStripper()
    # Start with a `[` so every chunk extends the unclosed opener.
    stripper.feed("[")
    for _ in range(10):
        stripper.feed("x" * 200)
        # Expose the private buffer — acceptable in a regression test.
        assert len(stripper._buf) <= _LITERAL_STRIPPER_BUF_CAP


def test_literal_stripper_long_plain_text_without_bracket_emits_promptly():
    """A 2 KB chunk without any bracket emits fully in one feed."""
    stripper = LiteralSrcStripper()
    big = "x" * 2048
    out = stripper.feed(big)
    assert out == big
    assert stripper._buf == ""


# ---------------------------------------------------------------------------
# Fix #13 — regex is gated by `'[' in text`.
# ---------------------------------------------------------------------------


class _CountingPattern:
    """Proxy around a compiled re.Pattern that tallies ``sub`` / ``subn`` calls."""

    def __init__(self, inner):
        self._inner = inner
        self.sub_calls = 0
        self.subn_calls = 0

    def sub(self, repl, text):
        self.sub_calls += 1
        return self._inner.sub(repl, text)

    def subn(self, repl, text):
        self.subn_calls += 1
        return self._inner.subn(repl, text)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_stream_rewriter_skips_regex_when_no_bracket(registry):
    """Chunks without any `[` must not invoke the leftover-tag regex."""
    counter = _CountingPattern(sr_mod._LEFTOVER_TAG_RE)
    with patch.object(sr_mod, "_LEFTOVER_TAG_RE", counter):
        rw = StreamRewriter(registry=registry)
        rw.feed("plain text without any bracket")
        rw.feed("more plain text too")
    assert counter.subn_calls == 0


def test_literal_stripper_skips_regex_when_no_bracket():
    counter = _CountingPattern(sr_mod._LEFTOVER_TAG_RE)
    with patch.object(sr_mod, "_LEFTOVER_TAG_RE", counter):
        stripper = LiteralSrcStripper()
        stripper.feed("plain text without any bracket")
        stripper.feed("more plain text too")
    assert counter.sub_calls == 0


def test_stream_rewriter_runs_regex_when_bracket_present(registry):
    """Chunks with `[` still get cleaned — baseline sanity."""
    counter = _CountingPattern(sr_mod._LEFTOVER_TAG_RE)
    with patch.object(sr_mod, "_LEFTOVER_TAG_RE", counter):
        rw = StreamRewriter(registry=registry)
        rw.feed("has a [src:bogus_tool_response] tag")
    assert counter.subn_calls >= 1
