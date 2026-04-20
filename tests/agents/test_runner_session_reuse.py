"""Tests for runner.create_session get-or-create semantics (Fix #2).

ADK's InMemorySessionService raises AlreadyExistsError on duplicate
session_id, so create_session must call get_session first and only
create when no existing session is found.
"""

from __future__ import annotations

import pytest

from beever_atlas.agents import runner as runner_mod


@pytest.fixture
def clean_sessions():
    """Give each test a fresh InMemorySessionService to prevent bleed-through."""
    from google.adk.sessions import InMemorySessionService

    saved = runner_mod._session_service
    runner_mod._session_service = InMemorySessionService()
    try:
        yield
    finally:
        runner_mod._session_service = saved


@pytest.mark.asyncio
async def test_first_call_with_session_id_creates_new_session(clean_sessions):
    session = await runner_mod.create_session(user_id="u1", session_id="s1")
    assert session.id == "s1"
    assert session.user_id == "u1"


@pytest.mark.asyncio
async def test_second_call_with_same_session_id_reuses(clean_sessions):
    first = await runner_mod.create_session(user_id="u1", session_id="s1")
    # Should NOT raise AlreadyExistsError.
    second = await runner_mod.create_session(user_id="u1", session_id="s1")
    assert second.id == first.id
    assert second.id == "s1"


@pytest.mark.asyncio
async def test_distinct_session_ids_create_distinct_sessions(clean_sessions):
    a = await runner_mod.create_session(user_id="u1", session_id="s1")
    b = await runner_mod.create_session(user_id="u1", session_id="s2")
    assert a.id != b.id
    assert a.id == "s1"
    assert b.id == "s2"


@pytest.mark.asyncio
async def test_no_session_id_generates_fresh_uuid_each_call(clean_sessions):
    a = await runner_mod.create_session(user_id="u1")
    b = await runner_mod.create_session(user_id="u1")
    assert a.id != b.id
    # Sanity: both look like uuid4 strings (36 chars, 4 dashes).
    assert len(a.id) == 36
    assert len(b.id) == 36


@pytest.mark.asyncio
async def test_session_state_initialized_on_create(clean_sessions):
    session = await runner_mod.create_session(
        user_id="u1", state={"foo": "bar"}, session_id="s-state"
    )
    assert session.state.get("foo") == "bar"
