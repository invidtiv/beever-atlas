"""Pydantic schemas for LLM-compiled wiki page output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CompiledPageContent(BaseModel):
    """LLM output for a compiled wiki page."""

    content: str = ""
    summary: str = ""


class CompiledCitation(BaseModel):
    """A citation extracted during compilation."""

    index: int
    author: str = ""
    timestamp: str = ""
    text_excerpt: str = ""
    permalink: str = ""
    media_type: str | None = None
    media_name: str | None = None


class CompiledPage(BaseModel):
    """Full compiled page output from LLM."""

    content: str = ""
    summary: str = ""
    citations: list[CompiledCitation] = Field(default_factory=list)
