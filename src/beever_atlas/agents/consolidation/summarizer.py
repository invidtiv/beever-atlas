"""Consolidation summarizer agent — generates topic and channel summaries."""
from __future__ import annotations

from google.adk.agents import LlmAgent
from google.genai import types

from beever_atlas.agents.schemas.consolidation import SummaryResult
from beever_atlas.llm import get_llm_provider


def create_summarizer(instruction: str, model=None) -> LlmAgent:
    """Create a summarizer LlmAgent with the given instruction.

    Args:
        instruction: The prompt template (cluster or channel level),
            with ``{context}`` already replaced by the caller.
        model: Optional model override. If None, resolved from config.
    """
    return LlmAgent(
        name="summarizer",
        model=model or get_llm_provider().resolve_model("summarizer"),
        instruction=instruction,
        output_key="summary_result",
        output_schema=SummaryResult,
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
