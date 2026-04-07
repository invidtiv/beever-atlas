from __future__ import annotations

from pydantic import BaseModel, Field


class ResolvedMessage(BaseModel):
    """A single message with coreference-resolved text."""

    index: int
    """Zero-based index of the message in the current batch."""

    text: str
    """Coreference-resolved text (pronouns replaced with explicit entities)."""


class CoreferenceResult(BaseModel):
    """Output schema for the coreference resolver agent."""

    resolved_messages: list[ResolvedMessage] = Field(default_factory=list)
    """Resolved messages from the current batch."""
