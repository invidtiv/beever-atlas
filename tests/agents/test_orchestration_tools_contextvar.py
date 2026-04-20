"""Tests for Fix #6: principal ContextVar resilience.

Covers:
- ``reset_principal`` swallows ValueError/LookupError and logs a warning.
- ``bound_principal`` context manager binds on entry and resets on exit.
- Nested ``bound_principal`` correctly restores the outer principal.
- Concurrent ``asyncio.gather`` with distinct ``bound_principal`` blocks
  keeps each task's principal isolated (no cross-task leak).
"""

from __future__ import annotations

import asyncio

import pytest

from beever_atlas.agents.tools import orchestration_tools as tools_mod
from beever_atlas.agents.tools.orchestration_tools import (
    _get_principal,
    bind_principal,
    bound_principal,
    reset_principal,
)


def test_bound_principal_sets_and_resets():
    assert _get_principal() is None
    with bound_principal("user:alice"):
        assert _get_principal() == "user:alice"
    assert _get_principal() is None


def test_bound_principal_resets_on_exception():
    assert _get_principal() is None
    with pytest.raises(RuntimeError):
        with bound_principal("user:bob"):
            assert _get_principal() == "user:bob"
            raise RuntimeError("boom")
    assert _get_principal() is None


def test_bound_principal_nested_restores_outer():
    with bound_principal("user:alice"):
        assert _get_principal() == "user:alice"
        with bound_principal("user:bob"):
            assert _get_principal() == "user:bob"
        assert _get_principal() == "user:alice"
    assert _get_principal() is None


def test_reset_principal_swallows_double_reset():
    """A double-reset (already-used token) must NOT raise.

    CPython raises ``RuntimeError`` on token reuse; the fix catches it and
    logs a warning instead. We assert the no-raise contract directly;
    log capture is verified by observing stderr in integration tests (the
    project's structured logger bypasses caplog).
    """
    token = bind_principal("user:alice")
    reset_principal(token)
    # This second call would raise pre-fix; post-fix it must return None.
    reset_principal(token)
    # No assertion needed beyond "did not raise" — but exercise the attr
    # to ensure the swallowed path didn't mutate the module.
    assert tools_mod.reset_principal is reset_principal


@pytest.mark.asyncio
async def test_concurrent_bound_principal_isolated_per_task():
    """Two concurrent tasks binding different principals must not leak
    each other's bindings — contextvars are copied per-task by asyncio."""
    observed: dict[str, str | None] = {}

    async def _worker(name: str) -> None:
        with bound_principal(f"user:{name}"):
            # Cede the event loop so both tasks interleave.
            await asyncio.sleep(0)
            observed[name] = _get_principal()
            await asyncio.sleep(0)

    await asyncio.gather(_worker("alice"), _worker("bob"))

    assert observed["alice"] == "user:alice"
    assert observed["bob"] == "user:bob"
    assert _get_principal() is None
