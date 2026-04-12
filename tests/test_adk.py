"""Tests for ADK agent scaffolding: tool stubs and runner."""

import pytest

from beever_atlas.agents.tools import ALL_TOOLS


class TestToolStubs:
    def test_all_11_tools_defined(self):
        assert len(ALL_TOOLS) == 11

    @pytest.mark.parametrize("tool_fn", ALL_TOOLS, ids=lambda f: f.__name__)
    def test_tool_has_docstring(self, tool_fn):
        assert tool_fn.__doc__ is not None
        assert len(tool_fn.__doc__) > 10

    def test_search_weaviate_hybrid_raises(self):
        from beever_atlas.agents.tools import search_weaviate_hybrid

        with pytest.raises(NotImplementedError, match="Weaviate"):
            search_weaviate_hybrid(query="test", channel_id="ch1")

    @pytest.mark.asyncio
    async def test_get_tier0_summary_is_callable(self):
        from beever_atlas.agents.tools import get_tier0_summary
        import inspect

        # get_tier0_summary is now implemented (async, uses weaviate store)
        assert inspect.iscoroutinefunction(get_tier0_summary)

    def test_traverse_neo4j_raises(self):
        from beever_atlas.agents.tools import traverse_neo4j

        with pytest.raises(NotImplementedError, match="Neo4j"):
            traverse_neo4j(entity_name="Alice")

    def test_search_tavily_raises(self):
        from beever_atlas.agents.tools import search_tavily

        with pytest.raises(NotImplementedError, match="Tavily"):
            search_tavily(query="test")

    def test_upsert_fact_raises(self):
        from beever_atlas.agents.tools import upsert_fact

        with pytest.raises(NotImplementedError, match="Weaviate"):
            upsert_fact(
                channel_id="ch1",
                memory="test fact",
                quality_score=7.0,
                topic_tags=["auth"],
                entity_tags=["Alice"],
                importance="high",
                user_name="alice",
                timestamp="2026-01-01T00:00:00Z",
                permalink="https://example.com",
            )

    def test_upsert_entity_raises(self):
        from beever_atlas.agents.tools import upsert_entity

        with pytest.raises(NotImplementedError, match="Neo4j"):
            upsert_entity(name="Alice", entity_type="Person", channel_id="ch1")

    def test_create_episodic_link_raises(self):
        from beever_atlas.agents.tools import create_episodic_link

        with pytest.raises(NotImplementedError, match="Neo4j"):
            create_episodic_link(
                entity_name="Alice",
                weaviate_id="uuid-123",
                channel_id="ch1",
                timestamp="2026-01-01T00:00:00Z",
            )

    def test_tool_names(self):
        expected_names = {
            "search_weaviate_hybrid",
            "get_tier0_summary",
            "get_tier1_clusters",
            "traverse_neo4j",
            "temporal_chain",
            "comprehensive_traverse",
            "get_episodic_weaviate_ids",
            "search_tavily",
            "upsert_fact",
            "upsert_entity",
            "create_episodic_link",
        }
        actual_names = {fn.__name__ for fn in ALL_TOOLS}
        assert actual_names == expected_names


class TestRunner:
    @pytest.mark.asyncio
    async def test_create_runner(self):
        from google.adk.agents import Agent

        from beever_atlas.agents.runner import create_runner

        agent = Agent(name="test_agent", model="gemini-2.0-flash-lite")
        runner = create_runner(agent)
        assert runner is not None
        assert runner.app_name == "beever_atlas"

    @pytest.mark.asyncio
    async def test_create_session(self):
        from beever_atlas.agents.runner import create_session

        session = await create_session(user_id="test_user")
        assert session is not None
        assert session.id is not None

    @pytest.mark.asyncio
    async def test_get_session_service(self):
        from beever_atlas.agents.runner import get_session_service

        service = get_session_service()
        assert service is not None
