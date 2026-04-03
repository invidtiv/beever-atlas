"""Tests for PlatformStore serialization helpers and credential decryption.

mongomock is not installed, so full CRUD tests that require a live Motor collection
are omitted. These tests cover _to_doc, _from_doc, and decrypt_connection_credentials
using mock data and a valid encryption key.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from beever_atlas.models.platform_connection import PlatformConnection

_VALID_KEY_HEX = secrets.token_hex(32)


def _patch_key(monkeypatch) -> None:
    from beever_atlas.infra import config

    monkeypatch.setenv("CREDENTIAL_MASTER_KEY", _VALID_KEY_HEX)
    config.get_settings.cache_clear()


def _make_store(monkeypatch) -> object:
    """Return a PlatformStore with a mock Motor collection."""
    from beever_atlas.stores.platform_store import PlatformStore

    mock_col = MagicMock()
    return PlatformStore(mock_col)


def _encrypted_conn(monkeypatch, **overrides) -> PlatformConnection:
    """Build a PlatformConnection with real encrypted credentials."""
    _patch_key(monkeypatch)
    from beever_atlas.infra.crypto import encrypt_credentials

    ciphertext, iv, tag = encrypt_credentials({"token": "xoxb-test"})
    defaults = dict(
        platform="slack",
        display_name="My Workspace",
        encrypted_credentials=ciphertext,
        credential_iv=iv,
        credential_tag=tag,
    )
    defaults.update(overrides)
    return PlatformConnection(**defaults)


class TestToDoc:
    def test_to_doc_returns_dict(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        conn = _encrypted_conn(monkeypatch)

        doc = store._to_doc(conn)

        assert isinstance(doc, dict)

    def test_to_doc_includes_all_model_fields(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        conn = _encrypted_conn(monkeypatch)

        doc = store._to_doc(conn)

        assert "id" in doc
        assert "platform" in doc
        assert "display_name" in doc
        assert "encrypted_credentials" in doc
        assert "credential_iv" in doc
        assert "credential_tag" in doc
        assert "selected_channels" in doc
        assert "status" in doc
        assert "source" in doc
        assert "created_at" in doc
        assert "updated_at" in doc

    def test_to_doc_preserves_field_values(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        conn = _encrypted_conn(monkeypatch)

        doc = store._to_doc(conn)

        assert doc["id"] == conn.id
        assert doc["platform"] == "slack"
        assert doc["display_name"] == "My Workspace"
        assert doc["status"] == "connected"
        assert doc["source"] == "ui"
        assert doc["selected_channels"] == []


class TestFromDoc:
    def test_from_doc_returns_platform_connection(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        conn = _encrypted_conn(monkeypatch)
        doc = store._to_doc(conn)

        result = store._from_doc(doc)

        assert isinstance(result, PlatformConnection)

    def test_from_doc_strips_mongodb_id_field(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        conn = _encrypted_conn(monkeypatch)
        doc = store._to_doc(conn)
        doc["_id"] = "some-mongo-object-id"

        result = store._from_doc(doc)

        assert not hasattr(result, "_id")

    def test_from_doc_preserves_all_field_values(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        conn = _encrypted_conn(monkeypatch, selected_channels=["C001", "C002"])
        doc = store._to_doc(conn)

        result = store._from_doc(doc)

        assert result.id == conn.id
        assert result.platform == conn.platform
        assert result.display_name == conn.display_name
        assert result.status == conn.status
        assert result.source == conn.source
        assert result.selected_channels == ["C001", "C002"]

    def test_to_doc_then_from_doc_round_trip_preserves_bytes(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        conn = _encrypted_conn(monkeypatch)
        doc = store._to_doc(conn)

        result = store._from_doc(doc)

        assert result.encrypted_credentials == conn.encrypted_credentials
        assert result.credential_iv == conn.credential_iv
        assert result.credential_tag == conn.credential_tag


class TestDecryptConnectionCredentials:
    def test_returns_original_credentials_dict(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        original = {"token": "xoxb-test", "team_id": "T999"}
        from beever_atlas.infra.crypto import encrypt_credentials

        ciphertext, iv, tag = encrypt_credentials(original)
        conn = PlatformConnection(
            platform="slack",
            display_name="Test",
            encrypted_credentials=ciphertext,
            credential_iv=iv,
            credential_tag=tag,
        )

        result = store.decrypt_connection_credentials(conn)

        assert result == original

    def test_returns_empty_dict_when_encrypted_empty(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        from beever_atlas.infra.crypto import encrypt_credentials

        ciphertext, iv, tag = encrypt_credentials({})
        conn = PlatformConnection(
            platform="discord",
            display_name="Test",
            encrypted_credentials=ciphertext,
            credential_iv=iv,
            credential_tag=tag,
        )

        result = store.decrypt_connection_credentials(conn)

        assert result == {}

    def test_tampered_credentials_raise_invalid_tag(self, monkeypatch):
        _patch_key(monkeypatch)
        store = _make_store(monkeypatch)
        from cryptography.exceptions import InvalidTag

        from beever_atlas.infra.crypto import encrypt_credentials

        ciphertext, iv, tag = encrypt_credentials({"token": "xoxb-test"})
        tampered = bytes([ciphertext[0] ^ 0xFF]) + ciphertext[1:]
        conn = PlatformConnection(
            platform="slack",
            display_name="Test",
            encrypted_credentials=tampered,
            credential_iv=iv,
            credential_tag=tag,
        )

        with pytest.raises(InvalidTag):
            store.decrypt_connection_credentials(conn)
