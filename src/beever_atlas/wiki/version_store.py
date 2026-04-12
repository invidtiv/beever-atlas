"""MongoDB-backed store for wiki version history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING

logger = logging.getLogger(__name__)

MAX_VERSIONS_DEFAULT = 10


class WikiVersionStore:
    """Stores versioned snapshots of wiki documents per channel."""

    def __init__(self, mongodb_uri: str, db_name: str = "beever_atlas") -> None:
        self._db = AsyncIOMotorClient(mongodb_uri)[db_name]
        self._collection = self._db["wiki_versions"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            [("channel_id", 1), ("version_number", 1)],
            unique=True,
        )
        await self._collection.create_index("channel_id")

    async def archive(self, channel_id: str, wiki_doc: dict) -> int:
        """Archive a wiki document as a new version. Returns the assigned version number."""
        next_version = await self._next_version_number(channel_id)
        version_doc = {
            "channel_id": channel_id,
            "version_number": next_version,
            "channel_name": wiki_doc.get("channel_name", ""),
            "platform": wiki_doc.get("platform", ""),
            "generated_at": wiki_doc.get("generated_at"),
            "archived_at": datetime.now(tz=UTC).isoformat(),
            "page_count": len(wiki_doc.get("pages", {})),
            "model": wiki_doc.get("metadata", {}).get("model", ""),
            "structure": wiki_doc.get("structure", {}),
            "overview": wiki_doc.get("overview", {}),
            "pages": wiki_doc.get("pages", {}),
            "metadata": wiki_doc.get("metadata", {}),
        }
        await self._collection.insert_one(version_doc)
        logger.info(
            "Archived wiki version %d for channel %s",
            next_version,
            channel_id,
        )
        return next_version

    async def cleanup(self, channel_id: str, max_versions: int = MAX_VERSIONS_DEFAULT) -> int:
        """Delete oldest versions exceeding the limit. Returns number of versions deleted."""
        count = await self._collection.count_documents({"channel_id": channel_id})
        if count <= max_versions:
            return 0

        excess = count - max_versions
        # Find the oldest excess versions
        cursor = (
            self._collection.find(
                {"channel_id": channel_id},
                {"version_number": 1},
            )
            .sort("version_number", 1)
            .limit(excess)
        )
        to_delete = [doc["version_number"] async for doc in cursor]
        if to_delete:
            result = await self._collection.delete_many(
                {"channel_id": channel_id, "version_number": {"$in": to_delete}}
            )
            logger.info(
                "Cleaned up %d old wiki versions for channel %s",
                result.deleted_count,
                channel_id,
            )
            return result.deleted_count
        return 0

    async def list_versions(self, channel_id: str) -> list[dict]:
        """Return version summaries sorted by version_number descending."""
        cursor = self._collection.find(
            {"channel_id": channel_id},
            {
                "_id": 0,
                "version_number": 1,
                "channel_id": 1,
                "generated_at": 1,
                "archived_at": 1,
                "page_count": 1,
                "model": 1,
            },
        ).sort("version_number", DESCENDING)
        return [doc async for doc in cursor]

    async def get_version(self, channel_id: str, version_number: int) -> dict | None:
        """Return a full version document or None."""
        return await self._collection.find_one(
            {"channel_id": channel_id, "version_number": version_number},
            {"_id": 0},
        )

    async def get_version_page(
        self, channel_id: str, version_number: int, page_id: str
    ) -> dict | None:
        """Return a single page from a version or None."""
        doc = await self._collection.find_one(
            {"channel_id": channel_id, "version_number": version_number},
            {"_id": 0, f"pages.{page_id}": 1},
        )
        if doc is None:
            return None
        return doc.get("pages", {}).get(page_id)

    async def count_versions(self, channel_id: str) -> int:
        """Return the number of archived versions for a channel."""
        return await self._collection.count_documents({"channel_id": channel_id})

    async def _next_version_number(self, channel_id: str) -> int:
        """Get the next version number for a channel."""
        latest = await self._collection.find_one(
            {"channel_id": channel_id},
            {"version_number": 1},
            sort=[("version_number", DESCENDING)],
        )
        if latest is None:
            return 1
        return latest["version_number"] + 1

    def close(self) -> None:
        self._db.client.close()
