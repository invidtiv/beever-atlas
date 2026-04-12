"""Weaviate-backed store for QA history (separate from MemoryFact collection)."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import Filter

logger = logging.getLogger(__name__)

QA_HISTORY_COLLECTION = "QAHistory"

_QA_HISTORY_PROPERTIES: list[tuple[str, DataType]] = [
    ("question", DataType.TEXT),
    ("answer", DataType.TEXT),
    ("citations_json", DataType.TEXT),
    ("channel_id", DataType.TEXT),
    ("user_id", DataType.TEXT),
    ("session_id", DataType.TEXT),
    ("timestamp", DataType.TEXT),
    ("is_deleted", DataType.BOOL),
]


class QAHistoryStore:
    """Manages the QAHistory collection in Weaviate for searchable Q&A history.

    Separate from MemoryFact — Q&A entries never appear in channel fact searches.
    """

    def __init__(self, url: str, api_key: str = "") -> None:
        self._url = url
        self._api_key = api_key
        self._client: weaviate.WeaviateClient | None = None

    async def startup(self) -> None:
        """Connect to Weaviate and ensure QAHistory schema exists."""

        def _connect() -> weaviate.WeaviateClient:
            from urllib.parse import urlparse

            parsed = urlparse(self._url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 8080)
            secure = parsed.scheme == "https"

            if host in ("localhost", "127.0.0.1") and not secure:
                return weaviate.connect_to_local(port=port, grpc_port=50051)

            headers: dict[str, str] = {}
            if self._api_key:
                headers["X-Weaviate-Api-Key"] = self._api_key
            return weaviate.connect_to_custom(
                http_host=host,
                http_port=port,
                http_secure=secure,
                grpc_host=host,
                grpc_port=50051,
                grpc_secure=secure,
                headers=headers,
            )

        self._client = await asyncio.to_thread(_connect)
        await self.ensure_schema()

    async def shutdown(self) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
            self._client = None

    async def ensure_schema(self) -> None:
        """Create QAHistory collection if it does not exist."""

        def _ensure() -> None:
            assert self._client is not None
            if self._client.collections.exists(QA_HISTORY_COLLECTION):
                # Migrate: add missing properties
                collection = self._client.collections.get(QA_HISTORY_COLLECTION)
                existing = {p.name for p in collection.config.get().properties}
                for name, dtype in _QA_HISTORY_PROPERTIES:
                    if name not in existing:
                        collection.config.add_property(Property(name=name, data_type=dtype))
                        logger.info("QAHistoryStore: added property %r to QAHistory", name)
                return
            self._client.collections.create(
                name=QA_HISTORY_COLLECTION,
                vectorizer_config=Configure.Vectorizer.none(),
                vector_index_config=Configure.VectorIndex.hnsw(),
                properties=[
                    Property(name=name, data_type=dtype)
                    for name, dtype in _QA_HISTORY_PROPERTIES
                ],
            )
            logger.info("QAHistoryStore: created QAHistory collection")

        await asyncio.to_thread(_ensure)

    def _collection(self):
        assert self._client is not None, "QAHistoryStore not started"
        if not self._client.collections.exists(QA_HISTORY_COLLECTION):
            logger.warning("QAHistoryStore: QAHistory collection missing, recreating")
            self._client.collections.create(
                name=QA_HISTORY_COLLECTION,
                vectorizer_config=Configure.Vectorizer.none(),
                vector_index_config=Configure.VectorIndex.hnsw(),
                properties=[
                    Property(name=name, data_type=dtype)
                    for name, dtype in _QA_HISTORY_PROPERTIES
                ],
            )
        return self._client.collections.get(QA_HISTORY_COLLECTION)

    async def write_qa_entry(
        self,
        question: str,
        answer: str,
        citations: list[dict],
        channel_id: str,
        user_id: str,
        session_id: str,
    ) -> str:
        """Write a Q&A pair to QAHistory. Returns the Weaviate UUID."""
        entry_id = str(uuid.uuid4())
        props = {
            "question": question,
            "answer": answer,
            "citations_json": json.dumps(citations),
            "channel_id": channel_id,
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "is_deleted": False,
        }

        def _write() -> str:
            collection = self._collection()
            collection.data.insert(properties=props, uuid=entry_id)
            return entry_id

        return await asyncio.to_thread(_write)

    async def search_qa_history(
        self,
        channel_id: str,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        """BM25 keyword search over QAHistory scoped to a channel.

        Filters out is_deleted=True entries. Returns list of
        {question, answer, citations, timestamp}.
        """

        def _search() -> list[dict]:
            collection = self._collection()
            channel_filter = Filter.by_property("channel_id").equal(channel_id)
            not_deleted = Filter.by_property("is_deleted").equal(False)
            combined = channel_filter & not_deleted
            result = collection.query.bm25(
                query=query,
                limit=limit,
                filters=combined,
            )
            entries = []
            for obj in result.objects:
                props = obj.properties
                try:
                    citations = json.loads(str(props.get("citations_json") or "[]"))
                except (json.JSONDecodeError, TypeError):
                    citations = []
                entries.append({
                    "question": props.get("question", ""),
                    "answer": props.get("answer", ""),
                    "citations": citations,
                    "timestamp": props.get("timestamp", ""),
                    "session_id": props.get("session_id", ""),
                    "id": str(obj.uuid),
                })
            return entries

        try:
            return await asyncio.to_thread(_search)
        except Exception:
            logger.exception("QAHistoryStore.search_qa_history failed")
            return []

    async def soft_delete(self, entry_id: str) -> None:
        """Mark a QAHistory entry as deleted (is_deleted=True)."""

        def _delete() -> None:
            collection = self._collection()
            collection.data.update(
                uuid=entry_id,
                properties={"is_deleted": True},
            )

        await asyncio.to_thread(_delete)
