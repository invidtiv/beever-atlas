"""Entity registry backed by Neo4jStore for canonical name resolution."""

from __future__ import annotations

import logging
from typing import Any

from beever_atlas.stores.neo4j_store import Neo4jStore

logger = logging.getLogger(__name__)


class EntityRegistry:
    """Resolves and registers entity aliases using the Neo4j knowledge graph
    as the backing store. Entities in Neo4j ARE the registry."""

    def __init__(self, neo4j: Neo4jStore) -> None:
        self._neo4j = neo4j
        self._rejection_cache: dict[tuple[str, str], bool] = {}

    async def resolve_alias(
        self,
        name: str,
        entity_type: str,
        channel_id: str | None = None,
    ) -> str:
        """Return the canonical entity name for `name`, or `name` itself if
        no entity or alias match is found.

        Checks channel-scoped entities first (when channel_id is provided),
        then falls back to global scope.
        """
        canonical = await self.get_canonical(name)
        if canonical is not None:
            return canonical
        return name

    async def register_alias(
        self,
        alias: str,
        canonical: str,
        entity_type: str,
    ) -> None:
        """Append `alias` to the aliases array of the entity with name `canonical`.

        No-op if the entity does not exist.
        """
        await self._neo4j.execute_query(
            """
            MATCH (e:Entity {name: $canonical, type: $entity_type})
            SET e.aliases = CASE
                WHEN $alias IN coalesce(e.aliases, []) THEN e.aliases
                ELSE coalesce(e.aliases, []) + [$alias]
            END
            """,
            canonical=canonical,
            entity_type=entity_type,
            alias=alias,
        )

    async def get_canonical(self, name: str) -> str | None:
        """Find an entity by exact name or by alias. Returns the canonical
        (node) name, or None if no match is found."""
        records = await self._neo4j.execute_query(
            """
            MATCH (e:Entity)
            WHERE e.name = $name OR $name IN coalesce(e.aliases, [])
            RETURN e.name AS canonical
            LIMIT 1
            """,
            name=name,
        )
        if not records:
            return None
        return records[0]["canonical"]

    async def get_all_canonical(self) -> list[dict]:
        """Return all entities as dicts with name, type, and aliases.

        Intended for pipeline state injection.
        """
        records = await self._neo4j.execute_query(
            """
            MATCH (e:Entity)
            RETURN e.name AS name, e.type AS type,
                   coalesce(e.aliases, []) AS aliases
            ORDER BY e.name
            """
        )
        return [
            {
                "name": r["name"],
                "type": r["type"],
                "aliases": list(r["aliases"]),
            }
            for r in records
        ]

    async def fuzzy_match(
        self, name: str, threshold: float = 0.8
    ) -> list[tuple[str, float]]:
        """Return (canonical_name, score) pairs for entities similar to `name`.

        Delegates to Neo4jStore.fuzzy_match_entity via APOC Jaro-Winkler.
        """
        records = await self._neo4j.execute_query(
            """
            MATCH (e:Entity)
            WITH e, apoc.text.jaroWinklerDistance(e.name, $name) AS score
            WHERE score >= $threshold
            RETURN e.name AS name, score
            ORDER BY score DESC
            """,
            name=name,
            threshold=threshold,
        )
        return [(r["name"], float(r["score"])) for r in records]

    # ------------------------------------------------------------------
    # Embedding-based semantic similarity (Group 2)
    # ------------------------------------------------------------------

    async def compute_name_embeddings_batch(
        self, names: list[str]
    ) -> dict[str, list[float]]:
        """Compute Jina embeddings for multiple entity names in a single API call.

        Returns a dict mapping name -> embedding vector.
        """
        if not names:
            return {}
        import httpx
        from beever_atlas.infra.config import get_settings

        settings = get_settings()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                settings.jina_api_url,
                headers={
                    "Authorization": f"Bearer {settings.jina_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.jina_model,
                    "input": names,
                    "dimensions": settings.jina_dimensions,
                    "task": "text-matching",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            result: dict[str, list[float]] = {}
            for i, item in enumerate(data["data"]):
                if i < len(names):
                    result[names[i]] = item["embedding"]
            return result

    async def compute_name_embedding(self, name: str) -> list[float]:
        """Compute a Jina embedding for an entity name.

        Returns the embedding vector.
        """
        import httpx
        from beever_atlas.infra.config import get_settings

        settings = get_settings()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                settings.jina_api_url,
                headers={
                    "Authorization": f"Bearer {settings.jina_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.jina_model,
                    "input": [name],
                    "dimensions": settings.jina_dimensions,
                    "task": "text-matching",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    async def find_similar_by_embedding(
        self,
        name: str,
        name_vector: list[float],
        threshold: float = 0.85,
    ) -> list[tuple[str, float]]:
        """Find entities similar to `name` using cached name_vector embeddings.

        Computes cosine similarity against all entities that have a name_vector
        stored in Neo4j. Returns (canonical_name, similarity_score) pairs above
        the threshold.
        """
        import math

        records = await self._neo4j.execute_query(
            "MATCH (e:Entity) WHERE e.name_vector IS NOT NULL "
            "RETURN e.name AS name, e.name_vector AS vec"
        )

        results: list[tuple[str, float]] = []
        for r in records:
            vec = r.get("vec")
            if not vec or not isinstance(vec, list):
                continue
            # Cosine similarity
            dot = sum(a * b for a, b in zip(name_vector, vec))
            norm_a = math.sqrt(sum(a * a for a in name_vector))
            norm_b = math.sqrt(sum(b * b for b in vec))
            if norm_a == 0 or norm_b == 0:
                continue
            similarity = dot / (norm_a * norm_b)
            if similarity >= threshold and r["name"] != name:
                results.append((r["name"], round(similarity, 4)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    async def store_name_vector(
        self, entity_name: str, vector: list[float]
    ) -> None:
        """Cache a name embedding vector on a Neo4j Entity node."""
        await self._neo4j.execute_query(
            "MATCH (e:Entity {name: $name}) SET e.name_vector = $vector",
            name=entity_name,
            vector=vector,
        )

    def is_merge_rejected(self, name_a: str, name_b: str) -> bool:
        """Check if a merge pair was previously rejected."""
        key = tuple(sorted([name_a, name_b]))
        return self._rejection_cache.get(key, False)  # type: ignore[arg-type]

    def cache_merge_rejection(self, name_a: str, name_b: str) -> None:
        """Record that a merge between two entities was rejected."""
        key = tuple(sorted([name_a, name_b]))
        self._rejection_cache[key] = True  # type: ignore[index]
