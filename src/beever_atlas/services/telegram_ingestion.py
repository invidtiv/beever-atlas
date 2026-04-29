"""Telegram Bot API update normalization and durable ingestion helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from beever_atlas.adapters.base import NormalizedMessage

TELEGRAM_MESSAGE_KEYS = (
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
)


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return str(value)


def _name_from_user(user: dict[str, Any]) -> str:
    name = " ".join(str(user.get(k) or "").strip() for k in ("first_name", "last_name")).strip()
    return name or str(user.get("username") or user.get("id") or "")


def _attachment(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {"type": kind}
    for source_key, dest_key in (
        ("file_id", "file_id"),
        ("file_unique_id", "file_unique_id"),
        ("file_name", "name"),
        ("mime_type", "mime_type"),
        ("file_size", "size"),
        ("emoji", "emoji"),
        ("set_name", "set_name"),
    ):
        if payload.get(source_key) is not None:
            item[dest_key] = payload[source_key]
    return item


def _attachments_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    if isinstance(message.get("photo"), list) and message["photo"]:
        largest = message["photo"][-1]
        if isinstance(largest, dict):
            attachments.append(_attachment("photo", largest))
    for key in ("document", "video", "audio", "voice", "animation", "sticker"):
        payload = message.get(key)
        if isinstance(payload, dict):
            attachments.append(_attachment(key, payload))
    return attachments


def _message_from_update(update: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    for key in TELEGRAM_MESSAGE_KEYS:
        value = update.get(key)
        if isinstance(value, dict):
            return key, value
    return None


def normalize_telegram_update(
    update: dict[str, Any],
    *,
    source: str = "telegram_polling",
) -> NormalizedMessage | None:
    """Convert one Telegram Bot API Update into a NormalizedMessage.

    Service-only updates are ignored here; their chat metadata can still be
    observed by callers that inspect the raw payload.
    """
    found = _message_from_update(update)
    if found is None:
        return None

    update_type, message = found
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("id") is None:
        return None

    content = _flatten_text(message.get("text") if "text" in message else message.get("caption"))
    attachments = _attachments_from_message(message)
    if not content and not attachments:
        return None

    sender = message.get("from")
    if isinstance(sender, dict):
        author = str(sender.get("id") or "")
        author_name = _name_from_user(sender)
    else:
        sender_chat = message.get("sender_chat") if isinstance(message.get("sender_chat"), dict) else {}
        author = str(sender_chat.get("id") or chat.get("id") or "")
        author_name = str(sender_chat.get("title") or chat.get("title") or author)

    chat_id = str(chat["id"])
    channel_name = str(
        chat.get("title")
        or " ".join(
            str(chat.get(k) or "").strip() for k in ("first_name", "last_name")
        ).strip()
        or chat.get("username")
        or chat_id
    )

    reply = message.get("reply_to_message")
    thread_id = None
    if isinstance(reply, dict) and reply.get("message_id") is not None:
        thread_id = str(reply["message_id"])

    raw_date = message.get("date")
    timestamp = (
        datetime.fromtimestamp(int(raw_date), tz=UTC)
        if raw_date is not None
        else datetime.now(tz=UTC)
    )

    return NormalizedMessage(
        content=content,
        author=author,
        platform="telegram",
        channel_id=chat_id,
        channel_name=channel_name,
        message_id=str(message.get("message_id", update.get("update_id", ""))),
        timestamp=timestamp,
        thread_id=thread_id,
        attachments=attachments,
        reactions=[],
        reply_count=0,
        raw_metadata={
            "source": source,
            "update_id": update.get("update_id"),
            "update_type": update_type,
            "chat_type": chat.get("type"),
            "raw": update,
        },
        author_name=author_name,
        author_image="",
    )


class TelegramUpdateIngestor:
    """Persist normalized Telegram updates and remember observed chats."""

    def __init__(self, *, source_store, platform_store) -> None:
        self._source_store = source_store
        self._platform_store = platform_store

    async def ingest_update(
        self,
        connection_id: str,
        update: dict[str, Any],
        *,
        source: str,
    ) -> list[NormalizedMessage]:
        message = normalize_telegram_update(update, source=source)
        if message is None:
            return []

        await self._source_store.upsert_message(connection_id, message, source=source)
        await self._append_observed_channel(connection_id, message.channel_id)
        return [message]

    async def ingest_updates(
        self,
        connection_id: str,
        updates: list[dict[str, Any]],
        *,
        source: str,
    ) -> list[NormalizedMessage]:
        messages: list[NormalizedMessage] = []
        for update in updates:
            messages.extend(
                await self.ingest_update(connection_id, update, source=source)
            )
        return messages

    async def _append_observed_channel(self, connection_id: str, channel_id: str) -> None:
        conn = await self._platform_store.get_connection(connection_id)
        if conn is None:
            return
        selected = list(conn.selected_channels or [])
        if channel_id in selected:
            return
        selected.append(channel_id)
        await self._platform_store.update_connection(connection_id, selected_channels=selected)


class TelegramBotApiClient:
    """Small async Telegram Bot API client for update transport management."""

    def __init__(self, bot_token: str, *, http_client: httpx.AsyncClient | None = None) -> None:
        self._bot_token = bot_token
        self._client = http_client or httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{bot_token}",
            timeout=35.0,
        )
        self._owns_client = http_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_webhook_info(self) -> dict[str, Any]:
        return await self._post("getWebhookInfo", {})

    async def get_updates(
        self,
        *,
        offset: int | None,
        timeout: int,
        allowed_updates: list[str],
        limit: int = 100,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "limit": limit,
            "allowed_updates": allowed_updates,
        }
        if offset is not None:
            payload["offset"] = offset
        return await self._post("getUpdates", payload)

    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> dict[str, Any]:
        return await self._post(
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
        )

    async def set_webhook(
        self,
        *,
        url: str,
        secret_token: str | None = None,
        allowed_updates: list[str] | None = None,
        drop_pending_updates: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "url": url,
            "drop_pending_updates": drop_pending_updates,
        }
        if secret_token:
            payload["secret_token"] = secret_token
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates
        return await self._post("setWebhook", payload)

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(f"/{method}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            raise RuntimeError(data.get("description") or f"Telegram {method} failed")
        return data


class TelegramPollingService:
    """Poll Telegram Bot API updates for connections configured for polling."""

    DEFAULT_ALLOWED_UPDATES = [
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
    ]

    def __init__(
        self,
        *,
        platform_store,
        source_store,
        state_collection,
        api_factory=None,
        timeout_seconds: int = 20,
        allowed_updates: list[str] | None = None,
    ) -> None:
        self._platform_store = platform_store
        self._source_store = source_store
        self._state_collection = state_collection
        self._api_factory = api_factory or (lambda token: TelegramBotApiClient(token))
        self._timeout_seconds = timeout_seconds
        self._allowed_updates = allowed_updates or self.DEFAULT_ALLOWED_UPDATES

    async def poll_connection(self, conn) -> dict[str, Any]:
        if conn.platform != "telegram" or conn.ingestion_mode != "polling":
            return {"status": "skipped", "stored_updates": 0}

        credentials = self._platform_store.decrypt_connection_credentials(conn)
        bot_token = credentials.get("bot_token") or credentials.get("botToken")
        if not bot_token:
            return {"status": "skipped", "stored_updates": 0, "reason": "missing_bot_token"}

        state = await self._state_collection.find_one({"connection_id": conn.id}) or {}
        offset = state.get("next_offset")
        api = self._api_factory(bot_token)
        close = getattr(api, "close", None)
        try:
            webhook_info = await api.get_webhook_info()
            webhook_url = (webhook_info.get("result") or {}).get("url") or ""
            if webhook_url:
                message = (
                    "Telegram polling is blocked because a webhook is configured. "
                    "Use deleteWebhook before polling."
                )
                await self._record_state(conn.id, {"last_error": message, "last_poll_at": _now()})
                return {
                    "status": "blocked_by_webhook",
                    "stored_updates": 0,
                    "webhook_url": webhook_url,
                }

            response = await api.get_updates(
                offset=offset,
                timeout=self._timeout_seconds,
                allowed_updates=self._allowed_updates,
            )
            updates = response.get("result") or []
            ingestor = TelegramUpdateIngestor(
                source_store=self._source_store,
                platform_store=self._platform_store,
            )
            await ingestor.ingest_updates(conn.id, updates, source="telegram_polling")

            fields: dict[str, Any] = {
                "last_poll_at": _now(),
                "last_error": None,
                "last_update_count": len(updates),
            }
            if updates:
                fields["next_offset"] = max(int(u["update_id"]) for u in updates) + 1
            await self._record_state(conn.id, fields)
            return {"status": "ok", "stored_updates": len(updates)}
        except Exception as exc:
            await self._record_state(conn.id, {"last_error": str(exc), "last_poll_at": _now()})
            raise
        finally:
            if close is not None:
                await close()

    async def poll_once(self) -> list[dict[str, Any]]:
        connections = await self._platform_store.list_connections()
        results: list[dict[str, Any]] = []
        for conn in connections:
            if conn.platform == "telegram" and conn.status == "connected":
                results.append(await self.poll_connection(conn))
        return results

    async def _record_state(self, connection_id: str, fields: dict[str, Any]) -> None:
        await self._state_collection.update_one(
            {"connection_id": connection_id},
            {
                "$set": {
                    "connection_id": connection_id,
                    "updated_at": _now(),
                    **fields,
                }
            },
            upsert=True,
        )


def _now() -> datetime:
    return datetime.now(tz=UTC)
