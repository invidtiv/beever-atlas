from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from beever_atlas.adapters.base import NormalizedMessage
from beever_atlas.services.source_messages import SourceMessageStore


class _AsyncCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def sort(self, field: str, direction: int):
        reverse = direction < 0
        self._docs = sorted(self._docs, key=lambda doc: doc.get(field), reverse=reverse)
        return self

    def limit(self, count: int):
        self._docs = self._docs[:count]
        return self

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._idx]
        self._idx += 1
        return doc


class _FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str, str, str], dict] = {}
        self.indexes: list[object] = []

    async def create_index(self, spec, **kwargs):
        self.indexes.append((spec, kwargs))

    async def update_one(self, filt: dict, update: dict, upsert: bool = False):
        key = (
            filt["platform"],
            filt["connection_id"],
            filt["channel_id"],
            filt["message_id"],
        )
        existing = self.docs.get(key, {})
        if upsert and "$setOnInsert" in update:
            existing = {**update["$setOnInsert"], **existing}
        if "$set" in update:
            existing.update(update["$set"])
        self.docs[key] = existing
        return SimpleNamespace(upserted_id=None, modified_count=1)

    def find(self, filt: dict):
        docs = []
        for doc in self.docs.values():
            if any(doc.get(k) != v for k, v in filt.items() if not isinstance(v, dict)):
                continue
            ts_filter = filt.get("timestamp")
            if isinstance(ts_filter, dict) and "$gt" in ts_filter:
                if not doc.get("timestamp") or doc["timestamp"] <= ts_filter["$gt"]:
                    continue
            docs.append(dict(doc))
        return _AsyncCursor(docs)


def _message(message_id: str, content: str = "hello") -> NormalizedMessage:
    return NormalizedMessage(
        content=content,
        author="user-1",
        author_name="Alice",
        platform="telegram",
        channel_id="-1001",
        channel_name="Atlas Test",
        message_id=message_id,
        timestamp=datetime(2026, 4, 29, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_source_message_upsert_is_idempotent_and_reads_normalized_messages() -> None:
    collection = _FakeCollection()
    store = SourceMessageStore(collection)

    await store.startup()
    await store.upsert_message("conn-1", _message("42", "first"), source="telegram_polling")
    await store.upsert_message("conn-1", _message("42", "edited"), source="telegram_polling")

    assert len(collection.docs) == 1

    messages = await store.list_messages("conn-1", "-1001")
    assert len(messages) == 1
    assert messages[0].content == "edited"
    assert messages[0].platform == "telegram"
    assert messages[0].raw_metadata["source"] == "telegram_polling"
    assert collection.indexes


@pytest.mark.asyncio
async def test_source_message_reads_incrementally_after_since_cursor() -> None:
    collection = _FakeCollection()
    store = SourceMessageStore(collection)
    older = _message("1", "older")
    newer = _message("2", "newer")
    newer.timestamp = datetime(2026, 4, 29, 11, 0, tzinfo=UTC)

    await store.upsert_message("conn-1", older, source="telegram_webhook")
    await store.upsert_message("conn-1", newer, source="telegram_webhook")

    messages = await store.list_messages(
        "conn-1",
        "-1001",
        since=datetime(2026, 4, 29, 10, 30, tzinfo=UTC),
    )

    assert [m.message_id for m in messages] == ["2"]
