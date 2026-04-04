"""Backfill script: compute and store name_vector embeddings for existing entities.

Usage:
    python -m scripts.backfill_name_vectors

Queries all Entity nodes in Neo4j that lack a name_vector property,
computes Jina embeddings for their names, and stores the vectors.
"""

from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    from beever_atlas.infra.config import get_settings
    from beever_atlas.stores import StoreClients, init_stores, get_stores

    settings = get_settings()
    stores = StoreClients.from_settings(settings)
    init_stores(stores)
    await stores.startup()

    # Find entities without name_vector
    names = await stores.graph.get_entities_missing_name_vectors()
    logger.info("Found %d entities without name_vector", len(names))

    if not names:
        logger.info("Nothing to backfill.")
        return

    # Batch compute embeddings (100 at a time)
    import httpx

    batch_size = 100
    computed = 0
    for i in range(0, len(names), batch_size):
        batch = names[i : i + batch_size]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    settings.jina_api_url,
                    headers={
                        "Authorization": f"Bearer {settings.jina_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.jina_model,
                        "input": batch,
                        "dimensions": settings.jina_dimensions,
                        "task": "text-matching",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            for j, item in enumerate(data["data"]):
                name = batch[j]
                vector = item["embedding"]
                await stores.entity_registry.store_name_vector(name, vector)
                computed += 1

            logger.info("Backfilled %d/%d entities", computed, len(names))

        except Exception:
            logger.error("Batch %d failed", i // batch_size, exc_info=True)

    logger.info("Backfill complete: %d/%d entities", computed, len(names))

    await stores.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
