"""Background reconciler for expired pending entities.

Periodically checks for pending entities that have exceeded their grace
period without gaining any relationships, and prunes them from Neo4j.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def prune_expired_orphans() -> int:
    """Prune pending entities that have exceeded the grace period.

    Returns the count of pruned entities.
    """
    from beever_atlas.infra.config import get_settings
    from beever_atlas.stores import get_stores

    settings = get_settings()
    stores = get_stores()

    try:
        count = await stores.graph.prune_expired_pending(
            grace_period_days=settings.orphan_grace_period_days,
        )
        if count > 0:
            logger.info(
                "OrphanReconciler: pruned %d expired pending entities (grace=%d days)",
                count,
                settings.orphan_grace_period_days,
            )
        return count
    except Exception:
        logger.warning("OrphanReconciler: prune failed", exc_info=True)
        return 0
