from __future__ import annotations

from pydantic import BaseModel


class SummaryResult(BaseModel):
    """Output schema for the consolidation summarizer agent."""

    summary_text: str = ""
    """Generated summary text for a topic cluster or channel."""
