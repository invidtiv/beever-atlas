"""WikiBuilder orchestrates the gather → compile → cache pipeline."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from beever_atlas.models.domain import WikiMetadata, WikiResponse
from beever_atlas.wiki.compiler import WikiCompiler
from beever_atlas.wiki.data_gatherer import WikiDataGatherer

logger = logging.getLogger(__name__)


class WikiBuilder:
    """Orchestrates the three-phase wiki generation pipeline."""

    def __init__(self, weaviate_store, graph_store, wiki_cache) -> None:
        self._gatherer = WikiDataGatherer(weaviate_store, graph_store)
        self._compiler = WikiCompiler()
        self._cache = wiki_cache
        self._active_generations: set[str] = set()

    async def generate_wiki(self, channel_id: str) -> WikiResponse:
        """Full pipeline: gather → compile → cache. Returns the WikiResponse."""
        if channel_id in self._active_generations:
            raise RuntimeError("already_running")

        self._active_generations.add(channel_id)
        try:
            start = time.monotonic()

            # Phase 1: gather
            data = await self._gatherer.gather(channel_id)

            # Phase 2: compile
            pages = await self._compiler.compile(data)

            # Phase 3: assemble
            channel_summary = data["channel_summary"]
            structure = self._compiler.build_structure(
                channel_id=channel_id,
                channel_name=channel_summary.channel_name,
                platform=channel_summary.channel_id and "slack",
                pages=pages,
            )

            duration_ms = int((time.monotonic() - start) * 1000)
            overview = pages.get("overview")
            if overview is None:
                raise RuntimeError("overview page compilation failed")

            metadata = WikiMetadata(
                memory_count=data["total_facts"],
                entity_count=data["total_entities"],
                media_count=channel_summary.media_count,
                page_count=len(pages),
                generation_duration_ms=duration_ms,
            )

            now = datetime.now(tz=UTC)
            wiki = WikiResponse(
                channel_id=channel_id,
                channel_name=channel_summary.channel_name,
                platform="slack",
                generated_at=now,
                is_stale=False,
                structure=structure,
                overview=overview,
                metadata=metadata,
            )

            wiki_dict = wiki.model_dump(mode="json")
            # Flatten pages into the cache doc
            wiki_dict["pages"] = {p_id: p.model_dump(mode="json") for p_id, p in pages.items()}

            await self._cache.save_wiki(channel_id, wiki_dict)
            logger.info(
                "WikiBuilder: generated wiki channel=%s pages=%d duration_ms=%d",
                channel_id, len(pages), duration_ms,
            )
            return wiki

        finally:
            self._active_generations.discard(channel_id)

    async def refresh_wiki(self, channel_id: str) -> None:
        """Async wrapper for background generation."""
        try:
            await self.generate_wiki(channel_id)
        except RuntimeError as exc:
            if "already_running" in str(exc):
                logger.info("WikiBuilder: generation already in progress for %s", channel_id)
            else:
                raise
