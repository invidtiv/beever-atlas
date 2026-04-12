"""MongoDB-backed store for chat history persistence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

CHAT_HISTORY_TTL_DAYS = 90
MAX_CONTEXT_TURNS = 10


class ChatHistoryStore:
    """Persists Q&A conversation sessions in MongoDB chat_history collection.

    Each session document contains: channel_id, user_id, session_id,
    messages[] (role, content, citations, tools_used, timestamp), created_at.
    TTL index auto-expires documents after 90 days.
    """

    def __init__(self, mongodb_uri: str, db_name: str = "beever_atlas") -> None:
        self._client = AsyncIOMotorClient(mongodb_uri)
        self._db = self._client[db_name]
        self._collection = self._db["chat_history"]

    async def startup(self) -> None:
        """Create indexes including the 90-day TTL index on created_at."""
        await self._collection.create_index("channel_id")
        await self._collection.create_index("user_id")
        await self._collection.create_index("session_id", unique=True)
        await self._collection.create_index(
            "created_at",
            expireAfterSeconds=CHAT_HISTORY_TTL_DAYS * 24 * 3600,
        )
        logger.info("ChatHistoryStore: indexes ensured (TTL=%d days)", CHAT_HISTORY_TTL_DAYS)

    def _now(self) -> datetime:
        return datetime.now(tz=UTC)

    async def create_session(
        self,
        session_id: str,
        channel_id: str,
        user_id: str,
    ) -> dict:
        """Create a new session document. Idempotent — safe to call if session exists."""
        doc = {
            "session_id": session_id,
            "channel_id": channel_id,
            "user_id": user_id,
            "messages": [],
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        try:
            await self._collection.insert_one(doc)
        except Exception:
            # Session may already exist (duplicate session_id) — ignore
            pass
        return {k: v for k, v in doc.items() if k != "_id"}

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        tools_used: list[str] | None = None,
    ) -> None:
        """Append a message to an existing session."""
        message = {
            "role": role,
            "content": content,
            "citations": citations or [],
            "tools_used": tools_used or [],
            "timestamp": self._now().isoformat(),
        }
        await self._collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": self._now()},
            },
        )

    async def load_session(self, session_id: str) -> dict | None:
        """Load a full session by ID. Returns None if not found."""
        return await self._collection.find_one(
            {"session_id": session_id}, {"_id": 0}
        )

    async def get_context_messages(self, session_id: str) -> list[dict]:
        """Return the last MAX_CONTEXT_TURNS messages for agent context window."""
        doc = await self._collection.find_one(
            {"session_id": session_id},
            {"_id": 0, "messages": {"$slice": -MAX_CONTEXT_TURNS}},
        )
        if doc is None:
            return []
        return doc.get("messages", [])

    async def list_sessions(
        self,
        channel_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict]:
        """Return paginated sessions for a user+channel, newest first.

        Each entry includes: session_id, created_at, first_question preview.
        """
        skip = (page - 1) * page_size
        cursor = (
            self._collection.find(
                {"channel_id": channel_id, "user_id": user_id},
                {
                    "_id": 0,
                    "session_id": 1,
                    "created_at": 1,
                    "messages": {"$slice": 1},
                },
            )
            .sort("created_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        results = []
        async for doc in cursor:
            first_q = ""
            msgs = doc.get("messages", [])
            if msgs:
                first_q = msgs[0].get("content", "")[:120]
            created = doc.get("created_at")
            results.append({
                "session_id": doc["session_id"],
                "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
                "first_question": first_q,
            })
        return results

    def close(self) -> None:
        self._client.close()
