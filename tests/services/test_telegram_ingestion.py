from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from beever_atlas.models.platform_connection import PlatformConnection
from beever_atlas.services.telegram_ingestion import (
    TelegramPollingService,
    TelegramUpdateIngestor,
    normalize_telegram_update,
)


def _telegram_connection(**overrides) -> PlatformConnection:
    defaults = dict(
        id="conn-telegram",
        platform="telegram",
        display_name="Telegram Test",
        encrypted_credentials=b"ciphertext",
        credential_iv=b"iv_12_bytes_",
        credential_tag=b"tag_16_bytes____",
        selected_channels=[],
        owner_principal_id="user:test",
    )
    defaults.update(overrides)
    return PlatformConnection(**defaults)


def test_normalize_telegram_update_flattens_rich_text_and_attachments() -> None:
    update = {
        "update_id": 100,
        "message": {
            "message_id": 42,
            "date": 1777466400,
            "chat": {"id": -1001, "title": "Atlas Test", "type": "supergroup"},
            "from": {"id": 7, "first_name": "Ada", "last_name": "Lovelace"},
            "text": ["Hello ", {"type": "bold", "text": "world"}],
            "reply_to_message": {"message_id": 12},
            "document": {"file_id": "file-1", "file_name": "notes.pdf", "mime_type": "application/pdf"},
        },
    }

    msg = normalize_telegram_update(update, source="telegram_polling")

    assert msg is not None
    assert msg.content == "Hello world"
    assert msg.platform == "telegram"
    assert msg.channel_id == "-1001"
    assert msg.channel_name == "Atlas Test"
    assert msg.author == "7"
    assert msg.author_name == "Ada Lovelace"
    assert msg.message_id == "42"
    assert msg.thread_id == "12"
    assert msg.timestamp == datetime.fromtimestamp(1777466400, tz=UTC)
    assert msg.attachments == [
        {
            "type": "document",
            "file_id": "file-1",
            "name": "notes.pdf",
            "mime_type": "application/pdf",
        }
    ]
    assert msg.raw_metadata["source"] == "telegram_polling"
    assert msg.raw_metadata["update_id"] == 100


def test_normalize_telegram_update_uses_caption_and_sender_chat_fallback() -> None:
    update = {
        "channel_post": {
            "message_id": 5,
            "date": 1777466400,
            "chat": {"id": "-1002", "title": "Atlas Announcements", "type": "channel"},
            "sender_chat": {"id": "-1002", "title": "Atlas Announcements"},
            "caption": "release image",
            "photo": [{"file_id": "small"}, {"file_id": "large"}],
        },
    }

    msg = normalize_telegram_update(update, source="telegram_webhook")

    assert msg is not None
    assert msg.content == "release image"
    assert msg.author == "-1002"
    assert msg.author_name == "Atlas Announcements"
    assert msg.attachments == [{"type": "photo", "file_id": "large"}]


def test_normalize_telegram_update_skips_service_update_without_message_text() -> None:
    assert normalize_telegram_update({"my_chat_member": {"chat": {"id": 1}}}) is None


@pytest.mark.asyncio
async def test_ingestor_persists_update_and_appends_observed_channel() -> None:
    conn = _telegram_connection()
    platform_store = SimpleNamespace(
        get_connection=AsyncMock(return_value=conn),
        update_connection=AsyncMock(return_value=None),
    )
    source_store = SimpleNamespace(upsert_message=AsyncMock())
    ingestor = TelegramUpdateIngestor(source_store=source_store, platform_store=platform_store)

    update = {
        "update_id": 101,
        "message": {
            "message_id": 9,
            "date": 1777466400,
            "chat": {"id": -1001, "title": "Atlas Test", "type": "group"},
            "from": {"id": 7, "first_name": "Ada"},
            "text": "hello",
        },
    }

    messages = await ingestor.ingest_update("conn-telegram", update, source="telegram_polling")

    assert len(messages) == 1
    source_store.upsert_message.assert_awaited_once()
    platform_store.update_connection.assert_awaited_once_with(
        "conn-telegram",
        selected_channels=["-1001"],
    )


class _FakeTelegramApi:
    def __init__(self, *, webhook_url: str = "", updates: list[dict] | None = None) -> None:
        self.webhook_url = webhook_url
        self.updates = updates or []
        self.get_updates_calls: list[dict] = []

    async def get_webhook_info(self) -> dict:
        return {"ok": True, "result": {"url": self.webhook_url}}

    async def get_updates(self, **kwargs) -> dict:
        self.get_updates_calls.append(kwargs)
        return {"ok": True, "result": self.updates}


class _FakeStateCollection:
    def __init__(self, state: dict | None = None) -> None:
        self.state = state
        self.updates: list[dict] = []

    async def find_one(self, filt: dict) -> dict | None:
        return self.state

    async def update_one(self, filt: dict, update: dict, upsert: bool = False):
        self.updates.append({"filter": filt, "update": update, "upsert": upsert})


@pytest.mark.asyncio
async def test_polling_uses_stored_offset_and_advances_after_storage() -> None:
    conn = _telegram_connection(ingestion_mode="polling")
    platform_store = SimpleNamespace(
        decrypt_connection_credentials=lambda c: {"bot_token": "123:abc"},
        get_connection=AsyncMock(return_value=conn),
        update_connection=AsyncMock(return_value=None),
    )
    source_store = SimpleNamespace(upsert_message=AsyncMock())
    state = _FakeStateCollection({"connection_id": conn.id, "next_offset": 10})
    api = _FakeTelegramApi(
        updates=[
            {
                "update_id": 10,
                "message": {
                    "message_id": 42,
                    "date": 1777466400,
                    "chat": {"id": -1001, "title": "Atlas Test", "type": "group"},
                    "from": {"id": 7, "first_name": "Ada"},
                    "text": "hello",
                },
            }
        ]
    )
    service = TelegramPollingService(
        platform_store=platform_store,
        source_store=source_store,
        state_collection=state,
        api_factory=lambda token: api,
    )

    result = await service.poll_connection(conn)

    assert result["stored_updates"] == 1
    assert api.get_updates_calls[0]["offset"] == 10
    assert state.updates[-1]["update"]["$set"]["next_offset"] == 11
    source_store.upsert_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_polling_does_not_advance_offset_when_storage_fails() -> None:
    conn = _telegram_connection(ingestion_mode="polling")
    platform_store = SimpleNamespace(
        decrypt_connection_credentials=lambda c: {"bot_token": "123:abc"},
        get_connection=AsyncMock(return_value=conn),
        update_connection=AsyncMock(return_value=None),
    )
    source_store = SimpleNamespace(upsert_message=AsyncMock(side_effect=RuntimeError("db down")))
    state = _FakeStateCollection({"connection_id": conn.id, "next_offset": 10})
    api = _FakeTelegramApi(
        updates=[
            {
                "update_id": 10,
                "message": {
                    "message_id": 42,
                    "date": 1777466400,
                    "chat": {"id": -1001, "title": "Atlas Test", "type": "group"},
                    "from": {"id": 7, "first_name": "Ada"},
                    "text": "hello",
                },
            }
        ]
    )
    service = TelegramPollingService(
        platform_store=platform_store,
        source_store=source_store,
        state_collection=state,
        api_factory=lambda token: api,
    )

    with pytest.raises(RuntimeError, match="db down"):
        await service.poll_connection(conn)

    assert not any("next_offset" in call["update"].get("$set", {}) for call in state.updates)


@pytest.mark.asyncio
async def test_polling_reports_active_webhook_as_blocker() -> None:
    conn = _telegram_connection(ingestion_mode="polling")
    platform_store = SimpleNamespace(
        decrypt_connection_credentials=lambda c: {"bot_token": "123:abc"},
        get_connection=AsyncMock(return_value=conn),
        update_connection=AsyncMock(return_value=None),
    )
    state = _FakeStateCollection()
    api = _FakeTelegramApi(webhook_url="https://example.com/api/webhooks/conn-telegram")
    service = TelegramPollingService(
        platform_store=platform_store,
        source_store=SimpleNamespace(upsert_message=AsyncMock()),
        state_collection=state,
        api_factory=lambda token: api,
    )

    result = await service.poll_connection(conn)

    assert result["status"] == "blocked_by_webhook"
    assert api.get_updates_calls == []
    assert "deleteWebhook" in state.updates[-1]["update"]["$set"]["last_error"]
