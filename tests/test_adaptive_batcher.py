"""Unit tests for token-aware adaptive batching."""

from beever_atlas.services.adaptive_batcher import (
    estimate_message_tokens,
    token_aware_batches,
)


def _msg(text: str = "", ts: str = "1", thread_ts: str | None = None, **extra):
    m = {"text": text, "ts": ts}
    if thread_ts:
        m["thread_ts"] = thread_ts
    m.update(extra)
    return m


class TestEstimateTokens:
    def test_basic_text(self):
        tokens = estimate_message_tokens(_msg("hello world"))  # 11 chars
        assert tokens == 50  # minimum overhead

    def test_long_text(self):
        tokens = estimate_message_tokens(_msg("x" * 900))
        assert tokens == 300  # 900 / 3

    def test_includes_thread_context(self):
        msg = _msg("short", thread_context="x" * 300)
        tokens = estimate_message_tokens(msg)
        assert tokens >= 100  # 300 / 3

    def test_includes_link_metadata(self):
        msg = _msg("hi", source_link_titles=["Title One"], source_link_descriptions=["Description text here"])
        tokens = estimate_message_tokens(msg)
        assert tokens >= 50

    def test_empty_message(self):
        tokens = estimate_message_tokens({})
        assert tokens == 50  # minimum overhead


class TestTokenAwareBatches:
    def test_empty_input(self):
        assert token_aware_batches([]) == []

    def test_all_fit_one_batch(self):
        msgs = [_msg("hello", ts=str(i)) for i in range(5)]
        batches = token_aware_batches(msgs, max_tokens=5000)
        assert len(batches) == 1
        assert len(batches[0]) == 5

    def test_splits_on_budget(self):
        # Each msg ~333 tokens (1000 chars / 3)
        msgs = [_msg("x" * 1000, ts=str(i)) for i in range(10)]
        batches = token_aware_batches(msgs, max_tokens=1000)
        assert len(batches) > 1
        for batch in batches:
            total = sum(estimate_message_tokens(m) for m in batch)
            # Each batch should be within budget (except oversized single groups)
            assert total <= 1000 or len(batch) == 1

    def test_single_message_exceeds_budget(self):
        msgs = [_msg("x" * 60000, ts="1")]  # ~20000 tokens
        batches = token_aware_batches(msgs, max_tokens=1000)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_thread_group_preservation(self):
        parent = _msg("parent message", ts="100")
        reply1 = _msg("reply one", ts="101", thread_ts="100")
        reply2 = _msg("reply two", ts="102", thread_ts="100")
        other = _msg("other message", ts="200")

        batches = token_aware_batches(
            [parent, reply1, reply2, other],
            max_tokens=200,  # small budget forces split
        )
        # Parent and replies must be in the same batch
        for batch in batches:
            ts_set = {m["ts"] for m in batch}
            if "100" in ts_set:
                assert "101" in ts_set and "102" in ts_set

    def test_chronological_order(self):
        msgs = [_msg("c", ts="3"), _msg("a", ts="1"), _msg("b", ts="2")]
        batches = token_aware_batches(msgs, max_tokens=50000)
        assert len(batches) == 1
        timestamps = [m["ts"] for m in batches[0]]
        assert timestamps == ["1", "2", "3"]

    def test_many_small_messages(self):
        msgs = [_msg("hi", ts=str(i)) for i in range(100)]
        batches = token_aware_batches(msgs, max_tokens=2000)
        total_msgs = sum(len(b) for b in batches)
        assert total_msgs == 100  # no messages lost
