"""Echo agent for validating the ADK pipeline without memory stores."""
from __future__ import annotations

from google.adk.agents import LlmAgent

from beever_atlas.agents.prompts.echo import ECHO_INSTRUCTION
from beever_atlas.llm import get_llm_provider


def create_echo_agent(model=None) -> LlmAgent:
    """Create the echo validation LlmAgent."""
    return LlmAgent(
        name="query_router_agent",
        description="Echo agent that validates the ADK pipeline. Returns the user's question with mock metadata.",
        model=model or get_llm_provider().resolve_model("echo"),
        instruction=ECHO_INSTRUCTION,
    )
