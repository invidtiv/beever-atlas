"""Tests for the PlatformConnection Pydantic model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from beever_atlas.models.platform_connection import PlatformConnection


def _minimal_conn(**overrides) -> PlatformConnection:
    """Build a PlatformConnection with minimal required fields, accepting overrides."""
    defaults = dict(
        platform="slack",
        display_name="Test Workspace",
        encrypted_credentials=b"ciphertext",
        credential_iv=b"iv_12_bytes_",
        credential_tag=b"tag_16_bytes____",
    )
    defaults.update(overrides)
    return PlatformConnection(**defaults)


class TestModelCreation:
    def test_creates_with_all_required_fields(self):
        conn = _minimal_conn()

        assert conn.platform == "slack"
        assert conn.display_name == "Test Workspace"
        assert conn.encrypted_credentials == b"ciphertext"
        assert conn.credential_iv == b"iv_12_bytes_"
        assert conn.credential_tag == b"tag_16_bytes____"

    def test_id_is_generated_as_uuid_string(self):
        conn = _minimal_conn()

        # Must be a valid UUID string.
        parsed = uuid.UUID(conn.id)
        assert str(parsed) == conn.id

    def test_two_instances_get_different_ids(self):
        conn1 = _minimal_conn()
        conn2 = _minimal_conn()

        assert conn1.id != conn2.id

    def test_explicit_id_is_preserved(self):
        custom_id = str(uuid.uuid4())
        conn = _minimal_conn(id=custom_id)

        assert conn.id == custom_id


class TestDefaultValues:
    def test_selected_channels_defaults_to_empty_list(self):
        conn = _minimal_conn()

        assert conn.selected_channels == []

    def test_status_defaults_to_connected(self):
        conn = _minimal_conn()

        assert conn.status == "connected"

    def test_source_defaults_to_ui(self):
        conn = _minimal_conn()

        assert conn.source == "ui"

    def test_error_message_defaults_to_none(self):
        conn = _minimal_conn()

        assert conn.error_message is None

    def test_created_at_is_timezone_aware_utc(self):
        conn = _minimal_conn()

        assert conn.created_at.tzinfo is not None
        assert conn.created_at.tzinfo == UTC

    def test_updated_at_is_timezone_aware_utc(self):
        conn = _minimal_conn()

        assert conn.updated_at.tzinfo is not None
        assert conn.updated_at.tzinfo == UTC

    def test_selected_channels_lists_are_independent_across_instances(self):
        """Mutable default factory must not share state across instances."""
        conn1 = _minimal_conn()
        conn2 = _minimal_conn()
        conn1.selected_channels.append("C001")

        assert conn2.selected_channels == []


class TestPlatformValidation:
    def test_slack_is_valid_platform(self):
        conn = _minimal_conn(platform="slack")

        assert conn.platform == "slack"

    def test_discord_is_valid_platform(self):
        conn = _minimal_conn(platform="discord")

        assert conn.platform == "discord"

    def test_teams_is_valid_platform(self):
        conn = _minimal_conn(platform="teams")

        assert conn.platform == "teams"

    def test_telegram_is_valid_platform(self):
        conn = _minimal_conn(platform="telegram")

        assert conn.platform == "telegram"

    def test_invalid_platform_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _minimal_conn(platform="whatsapp")

    def test_empty_platform_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _minimal_conn(platform="")


class TestSourceValidation:
    def test_ui_is_valid_source(self):
        conn = _minimal_conn(source="ui")

        assert conn.source == "ui"

    def test_env_is_valid_source(self):
        conn = _minimal_conn(source="env")

        assert conn.source == "env"

    def test_invalid_source_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _minimal_conn(source="api")


class TestStatusValidation:
    def test_connected_is_valid_status(self):
        conn = _minimal_conn(status="connected")

        assert conn.status == "connected"

    def test_disconnected_is_valid_status(self):
        conn = _minimal_conn(status="disconnected")

        assert conn.status == "disconnected"

    def test_error_is_valid_status(self):
        conn = _minimal_conn(status="error")

        assert conn.status == "error"

    def test_invalid_status_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _minimal_conn(status="pending")
