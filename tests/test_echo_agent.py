"""Tests for the echo agent and model configuration."""

from __future__ import annotations


class TestEchoAgent:
    def test_agent_name(self):
        from beever_atlas.agents.query.echo import create_echo_agent

        agent = create_echo_agent(model="gemini-2.5-flash")
        assert agent.name == "query_router_agent"

    def test_agent_has_description(self):
        from beever_atlas.agents.query.echo import create_echo_agent

        agent = create_echo_agent(model="gemini-2.5-flash")
        assert agent.description
        assert "echo" in agent.description.lower()

    def test_agent_has_instruction(self):
        from beever_atlas.agents.query.echo import create_echo_agent

        agent = create_echo_agent(model="gemini-2.5-flash")
        assert agent.instruction
        assert "echo" in agent.instruction.lower()


class TestRootAgentExport:
    def test_get_root_agent_returns_echo_agent(self):
        from beever_atlas.llm.provider import LLMProvider, init_llm_provider
        from beever_atlas.infra.config import Settings

        # Initialize provider for get_root_agent() which calls create_echo_agent()
        settings = Settings(google_api_key="test")
        init_llm_provider(settings)

        from beever_atlas.agents import get_root_agent

        agent = get_root_agent()
        assert agent.name == "query_router_agent"
