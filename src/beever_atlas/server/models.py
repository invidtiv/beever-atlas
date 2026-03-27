"""Pydantic response models for the REST API."""

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    """Health status for a single dependency."""

    status: str  # "up" or "down"
    latency_ms: float
    error: str | None = None


class HealthResponse(BaseModel):
    """Overall system health response for GET /api/health."""

    status: str  # "healthy", "degraded", or "unhealthy"
    components: dict[str, ComponentHealth]
    checked_at: str  # ISO 8601 timestamp
