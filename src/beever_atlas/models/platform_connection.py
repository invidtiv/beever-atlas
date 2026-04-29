"""Platform connection model for self-service integrations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PlatformConnection(BaseModel):
    """Persisted record of a connected chat platform."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: Literal["slack", "discord", "teams", "telegram", "mattermost", "file"]
    display_name: str
    encrypted_credentials: bytes
    credential_iv: bytes
    credential_tag: bytes
    selected_channels: list[str] = Field(default_factory=list)
    ingestion_mode: Literal["polling", "webhook"] | None = None
    status: Literal["connected", "disconnected", "error"] = "connected"
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    source: Literal["ui", "env"] = "ui"
    # Principal id (see `infra/auth.Principal.id`) of the user who created this
    # connection. `None` on documents written before RES-177; the platform
    # store's startup backfill rewrites `None` to the shared sentinel
    # ``"legacy:shared"`` so multi-tenant deployments have a single target
    # for explicit ownership assignment.
    owner_principal_id: str | None = None

    @model_validator(mode="after")
    def _default_telegram_ingestion_mode(self) -> "PlatformConnection":
        if self.platform == "telegram" and self.ingestion_mode is None:
            self.ingestion_mode = "polling"
        return self
