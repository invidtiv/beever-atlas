from __future__ import annotations

from pydantic import BaseModel, Field

from beever_atlas.agents.schemas.extraction import ExtractedEntity, ExtractedRelationship


class MergeRecord(BaseModel):
    canonical: str
    merged_from: list[str]


class ValidationResult(BaseModel):
    """Output schema for the CrossBatchValidatorAgent."""

    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]
    merges: list[MergeRecord]


class ContradictionResult(BaseModel):
    """A single detected contradiction between a new fact and an existing fact."""

    existing_fact_id: str
    """UUID of the contradicted existing fact."""

    confidence: float
    """0.0–1.0 confidence that this is a genuine contradiction."""

    reason: str = ""
    """Brief explanation of why this is a contradiction."""


class ContradictionReport(BaseModel):
    """Output schema for contradiction detection."""

    contradictions: list[ContradictionResult] = Field(default_factory=list)
    """List of detected contradictions (usually 0 or 1)."""
