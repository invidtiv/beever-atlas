"""Durable local source-message storage for webhook, polling, and imports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection

from beever_atlas.adapters.base import ChannelInfo, NormalizedMessage


def _coerce_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class SourceMessageStore:
    """Mongo-backed raw message store used before the extraction pipeline."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    async def startup(self) -> None:
        await self._col.create_index(
            [
                ("platform", 1),
                ("connection_id", 1),
                ("channel_id", 1),
                ("message_id", 1),
            ],
            unique=True,
        )
        await self._col.create_index([("channel_id", 1), ("timestamp", 1)])
        await self._col.create_index([("connection_id", 1), ("channel_id", 1), ("timestamp", 1)])

    async def upsert_message(
        self,
        connection_id: str,
        message: NormalizedMessage,
        *,
        source: str,
    ) -> None:
        now = datetime.now(tz=UTC)
        raw_metadata = dict(message.raw_metadata or {})
        raw_metadata["source"] = source
        doc = {
            "connection_id": connection_id,
            "platform": message.platform,
            "channel_id": message.channel_id,
            "channel_name": message.channel_name,
            "message_id": message.message_id,
            "timestamp": message.timestamp,
            "timestamp_iso": message.timestamp.isoformat(),
            "content": message.content,
            "author": message.author,
            "author_name": message.author_name,
            "author_image": message.author_image,
            "thread_id": message.thread_id,
            "attachments": message.attachments,
            "reactions": message.reactions,
            "reply_count": message.reply_count,
            "raw_metadata": raw_metadata,
            "source": source,
            "updated_at": now,
        }
        await self._col.update_one(
            {
                "platform": message.platform,
                "connection_id": connection_id,
                "channel_id": message.channel_id,
                "message_id": message.message_id,
            },
            {
                "$set": doc,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def upsert_messages(
        self,
        connection_id: str,
        messages: list[NormalizedMessage],
        *,
        source: str,
    ) -> None:
        for message in messages:
            await self.upsert_message(connection_id, message, source=source)

    async def list_messages(
        self,
        connection_id: str,
        channel_id: str,
        *,
        since: datetime | str | None = None,
        limit: int | None = None,
    ) -> list[NormalizedMessage]:
        query: dict[str, Any] = {
            "connection_id": connection_id,
            "channel_id": channel_id,
        }
        if since is not None:
            query["timestamp"] = {"$gt": _coerce_dt(since)}

        cursor = self._col.find(query).sort("timestamp", 1)
        if limit is not None and limit > 0:
            cursor = cursor.limit(limit)

        messages: list[NormalizedMessage] = []
        async for doc in cursor:
            messages.append(self._from_doc(doc))
        return messages

    async def list_channels(self, connection_id: str) -> list[ChannelInfo]:
        pipeline = [
            {"$match": {"connection_id": connection_id}},
            {
                "$group": {
                    "_id": "$channel_id",
                    "name": {"$last": "$channel_name"},
                    "platform": {"$last": "$platform"},
                    "last_seen": {"$max": "$timestamp"},
                }
            },
            {"$sort": {"name": 1}},
        ]
        channels: list[ChannelInfo] = []
        async for doc in self._col.aggregate(pipeline):
            channels.append(
                ChannelInfo(
                    channel_id=str(doc.get("_id", "")),
                    name=doc.get("name") or str(doc.get("_id", "")),
                    platform=doc.get("platform") or "telegram",
                    is_member=True,
                    connection_id=connection_id,
                )
            )
        return channels

    def _from_doc(self, doc: dict[str, Any]) -> NormalizedMessage:
        ts = _coerce_dt(doc.get("timestamp") or doc.get("timestamp_iso"))
        raw_metadata = dict(doc.get("raw_metadata") or {})
        if doc.get("source"):
            raw_metadata.setdefault("source", doc["source"])
        return NormalizedMessage(
            content=doc.get("content", ""),
            author=doc.get("author", ""),
            platform=doc.get("platform", ""),
            channel_id=doc.get("channel_id", ""),
            channel_name=doc.get("channel_name", doc.get("channel_id", "")),
            message_id=doc.get("message_id", ""),
            timestamp=ts,
            thread_id=doc.get("thread_id"),
            attachments=doc.get("attachments", []),
            reactions=doc.get("reactions", []),
            reply_count=doc.get("reply_count", 0),
            raw_metadata=raw_metadata,
            author_name=doc.get("author_name", ""),
            author_image=doc.get("author_image", "") or "",
        )
