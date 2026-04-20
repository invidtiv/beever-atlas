"""Admin-token-gated endpoints that must be available in production.

Distinct from :mod:`beever_atlas.api.dev`, which is mounted only when
``BEEVER_ENV=development``. Routes here run in every environment and are
used by operators (never by end users or the dashboard UI directly).

Auth: ``X-Admin-Token`` header compared against ``BEEVER_ADMIN_TOKEN`` via
:func:`~beever_atlas.infra.auth.require_admin`. User and MCP tokens are NOT
accepted.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from beever_atlas.infra.auth import require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
logger = logging.getLogger(__name__)


@router.get("/mcp-metrics")
async def mcp_metrics() -> dict:
    """Return an aggregated snapshot of MCP tool call metrics (task 7.6).

    Read-only operator view — summarises the in-memory rolling-window counter
    maintained by :mod:`beever_atlas.infra.mcp_metrics`. Shape:

        {
          "window_seconds": 3600,
          "total_calls": int,
          "distinct_principals": int,
          "by_outcome":       {"ok": int, "rate_limited": int, ...},
          "by_principal_tool": [{principal, tool, outcome, count}, ...],
          "by_tool_latency":  {tool: {count, avg_ms, p95_ms}, ...}
        }

    Per-process only — in multi-worker deploys each process reports its own
    slice. An aggregating UI layer can sum them. Principals are the full
    ``mcp:<hash>`` tokens (non-reversible; safe to expose to the admin).
    """
    from beever_atlas.infra import mcp_metrics as metrics_mod

    snapshot = metrics_mod.snapshot_counters()
    return snapshot


@router.post("/mcp-metrics/reset")
async def mcp_metrics_reset() -> dict:
    """Clear the in-memory rolling-window counter. Ops use only."""
    from beever_atlas.infra import mcp_metrics as metrics_mod

    metrics_mod.reset_counters()
    return {"status": "reset"}


__all__ = ["router"]
