from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from beever_atlas.services import sync_runner as sync_runner_module
from beever_atlas.services.batch_processor import BatchResult
from beever_atlas.adapters.base import NormalizedMessage
from beever_atlas.models.platform_connection import PlatformConnection


@dataclass
class _Msg:
    timestamp: datetime


class _InclusiveSinceAdapter:
    def __init__(self, messages: list[_Msg]) -> None:
        self.messages = messages
        self.calls = 0

    async def fetch_history(
        self,
        channel_id: str,
        since: datetime | None,
        limit: int,
        order: str = "desc",
    ) -> list[_Msg]:
        self.calls += 1
        if since is None:
            return self.messages[:2]
        return [m for m in self.messages if m.timestamp >= since][:2]


class _Status:
    def __init__(
        self,
        *,
        id: str,
        status: str,
        started_at: datetime,
        processed_messages: int = 0,
        total_messages: int = 0,
        current_batch: int = 0,
    ) -> None:
        self.id = id
        self.status = status
        self.started_at = started_at
        self.processed_messages = processed_messages
        self.total_messages = total_messages
        self.current_batch = current_batch


@pytest.mark.asyncio
async def test_fetch_all_messages_filters_inclusive_cursor_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    t1 = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 3, 1, 11, 0, tzinfo=UTC)
    t3 = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    adapter = _InclusiveSinceAdapter([_Msg(t1), _Msg(t2), _Msg(t3)])

    monkeypatch.setattr(sync_runner_module, "get_adapter", lambda: adapter)
    monkeypatch.setattr(
        sync_runner_module,
        "get_settings",
        lambda: SimpleNamespace(sync_max_messages=100),
    )

    runner = sync_runner_module.SyncRunner()
    result = await runner._fetch_all_messages("C123", adapter=adapter)

    assert [m.timestamp for m in result] == [t1, t2, t3]
    assert adapter.calls == 3


@pytest.mark.asyncio
async def test_fetch_all_messages_parses_iso_since_string(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_since: datetime | None = None

    class _Adapter:
        async def fetch_history(
            self,
            channel_id: str,
            since: datetime | None,
            limit: int,
            order: str = "desc",
        ) -> list[_Msg]:
            nonlocal seen_since
            seen_since = since
            return []

    _adapter_instance = _Adapter()
    monkeypatch.setattr(sync_runner_module, "get_adapter", lambda: _adapter_instance)
    monkeypatch.setattr(
        sync_runner_module,
        "get_settings",
        lambda: SimpleNamespace(sync_max_messages=100),
    )

    runner = sync_runner_module.SyncRunner()
    await runner._fetch_all_messages(
        "C123", adapter=_adapter_instance, since="2026-03-15T00:00:00Z"
    )

    assert isinstance(seen_since, datetime)
    assert seen_since == datetime(2026, 3, 15, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_run_sync_marks_job_failed_when_batches_have_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class _Mongo:
        async def complete_sync_job(
            self,
            job_id: str,
            status: str,
            errors: list[str] | None = None,
            failed_stage: str | None = None,
        ) -> None:
            calls["complete"] = {"job_id": job_id, "status": status, "errors": errors}

        async def log_activity(
            self, event_type: str, channel_id: str, details: dict[str, object]
        ) -> None:
            calls["activity"] = {
                "event_type": event_type,
                "channel_id": channel_id,
                "details": details,
            }

        async def update_channel_sync_state(
            self, channel_id: str, last_sync_ts: str, increment: int = 0, **kwargs
        ) -> None:
            calls["sync_state"] = {
                "channel_id": channel_id,
                "last_sync_ts": last_sync_ts,
                "increment": increment,
            }

    stores = SimpleNamespace(mongodb=_Mongo())
    monkeypatch.setattr(sync_runner_module, "get_stores", lambda: stores)

    async def _fake_resolve_policy(channel_id):
        from types import SimpleNamespace as NS

        return NS(ingestion=NS(), sync=NS(max_messages=100))

    monkeypatch.setattr(
        "beever_atlas.services.sync_runner.resolve_effective_policy",
        _fake_resolve_policy,
        raising=False,
    )

    async def _process_messages(**kwargs) -> BatchResult:
        return BatchResult(
            total_facts=0,
            total_entities=0,
            errors=[{"batch_num": 0, "error": "boom"}],
        )

    runner = sync_runner_module.SyncRunner()
    runner._batch_processor = SimpleNamespace(process_messages=_process_messages)

    await runner._run_sync(
        job_id="job-1",
        channel_id="C123",
        channel_name="general",
        messages=[],
    )

    complete = calls.get("complete")
    assert isinstance(complete, dict)
    assert complete["status"] == "failed"
    activity = calls.get("activity")
    assert isinstance(activity, dict)
    assert activity["event_type"] == "sync_failed"


@pytest.mark.asyncio
async def test_start_sync_recovers_stale_running_job(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    now = datetime(2026, 3, 30, 13, 30, tzinfo=UTC)
    stale = _Status(
        id="job-stale",
        status="running",
        started_at=now,
        processed_messages=0,
        total_messages=9,
        current_batch=0,
    )

    class _Mongo:
        async def get_sync_status(self, channel_id: str):
            calls["get_sync_status"] = channel_id
            return stale

        async def get_channel_sync_state(self, channel_id: str):
            return None

        async def complete_sync_job(
            self, job_id: str, status: str, errors: list[str] | None = None
        ) -> None:
            calls["complete_sync_job"] = {"job_id": job_id, "status": status, "errors": errors}

        async def create_sync_job(
            self,
            channel_id: str,
            sync_type: str,
            total_messages: int,
            batch_size: int,
            parent_messages: int = 0,
            **kwargs,
        ):
            calls["create_sync_job"] = {
                "channel_id": channel_id,
                "sync_type": sync_type,
                "total_messages": total_messages,
                "parent_messages": parent_messages,
                "batch_size": batch_size,
                **kwargs,
            }
            return SimpleNamespace(id="job-new")

    class _Adapter:
        async def fetch_history(self, channel_id: str, since, limit: int, order: str = "desc"):
            return []

        async def get_channel_info(self, channel_id: str):
            return SimpleNamespace(name="all-testing")

    class _FakeCollection:
        def find(self, *args, **kwargs):
            return self

        def to_list(self, length=None):
            async def _empty():
                return []

            return _empty()

    class _FakeDb:
        def __getitem__(self, name):
            return _FakeCollection()

    mongo = _Mongo()
    mongo.db = _FakeDb()
    stores = SimpleNamespace(mongodb=mongo)
    monkeypatch.setattr(sync_runner_module, "get_stores", lambda: stores)
    monkeypatch.setattr(
        sync_runner_module,
        "get_settings",
        lambda: SimpleNamespace(
            sync_max_messages=100, sync_batch_size=50, stale_job_threshold_hours=2
        ),
    )
    monkeypatch.setattr(sync_runner_module, "get_adapter", lambda: _Adapter())

    import beever_atlas.services.policy_resolver as _policy_mod

    async def _fake_policy(channel_id):
        return SimpleNamespace(sync=SimpleNamespace(max_messages=100), ingestion=SimpleNamespace())

    monkeypatch.setattr(_policy_mod, "resolve_effective_policy", _fake_policy)

    runner = sync_runner_module.SyncRunner()

    async def _fake_resolve_conn(channel_id, connection_id):
        return None

    runner._resolve_connection_id = _fake_resolve_conn

    job_id = await runner.start_sync("C0AMY9QSPB2")

    assert job_id == "job-new"
    completed = calls.get("complete_sync_job")
    assert isinstance(completed, dict)
    assert completed["job_id"] == "job-stale"
    assert completed["status"] == "failed"


def test_has_active_sync_returns_false_for_done_task() -> None:
    runner = sync_runner_module.SyncRunner()

    async def _noop() -> None:
        return None

    async def _run() -> None:
        task = asyncio.create_task(_noop())
        runner._active_tasks["C123"] = task
        await task
        assert runner.has_active_sync("C123") is False

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_start_sync_reads_telegram_messages_from_source_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    telegram_conn = PlatformConnection(
        id="conn-telegram",
        platform="telegram",
        display_name="Telegram",
        encrypted_credentials=b"ciphertext",
        credential_iv=b"iv_12_bytes_",
        credential_tag=b"tag_16_bytes____",
        selected_channels=["-1001"],
    )
    source_messages = [
        NormalizedMessage(
            content="hello telegram",
            author="7",
            author_name="Ada",
            platform="telegram",
            channel_id="-1001",
            channel_name="Atlas Test",
            message_id="42",
            timestamp=datetime(2026, 4, 29, 10, 0, tzinfo=UTC),
        )
    ]

    class _Mongo:
        class _EmptyCollection:
            def find(self, *args, **kwargs):
                return self

            async def to_list(self, length=None):
                return []

        db = {"source_messages": object(), "sync_jobs": _EmptyCollection()}

        async def get_sync_status(self, channel_id: str):
            return None

        async def get_channel_sync_state(self, channel_id: str):
            return None

        async def create_sync_job(
            self,
            channel_id: str,
            sync_type: str,
            total_messages: int,
            batch_size: int,
            parent_messages: int = 0,
            **kwargs,
        ):
            calls["create_sync_job"] = {
                "channel_id": channel_id,
                "sync_type": sync_type,
                "total_messages": total_messages,
                "parent_messages": parent_messages,
                "batch_size": batch_size,
                **kwargs,
            }
            return SimpleNamespace(id="job-telegram")

    class _Platform:
        async def get_connection(self, connection_id: str):
            assert connection_id == "conn-telegram"
            return telegram_conn

    class _FakeSourceStore:
        def __init__(self, collection):
            calls["collection"] = collection

        async def list_messages(self, connection_id: str, channel_id: str, since=None, limit=None):
            calls["list_messages"] = {
                "connection_id": connection_id,
                "channel_id": channel_id,
                "since": since,
                "limit": limit,
            }
            return source_messages

    stores = SimpleNamespace(mongodb=_Mongo(), platform=_Platform())
    monkeypatch.setattr(sync_runner_module, "get_stores", lambda: stores)
    monkeypatch.setattr(sync_runner_module, "SourceMessageStore", _FakeSourceStore, raising=False)
    monkeypatch.setattr(
        sync_runner_module,
        "get_settings",
        lambda: SimpleNamespace(
            sync_max_messages=100, sync_batch_size=50, stale_job_threshold_hours=2
        ),
    )

    import beever_atlas.services.policy_resolver as _policy_mod

    async def _fake_policy(channel_id):
        return SimpleNamespace(sync=SimpleNamespace(max_messages=100), ingestion=SimpleNamespace())

    monkeypatch.setattr(_policy_mod, "resolve_effective_policy", _fake_policy)

    runner = sync_runner_module.SyncRunner()

    async def _fake_run_sync(**kwargs):
        calls["run_sync"] = kwargs

    runner._run_sync = _fake_run_sync

    job_id = await runner.start_sync("-1001", connection_id="conn-telegram")

    assert job_id == "job-telegram"
    assert calls["list_messages"] == {
        "connection_id": "conn-telegram",
        "channel_id": "-1001",
        "since": None,
        "limit": 100,
    }
    assert calls["create_sync_job"]["total_messages"] == 1
    await runner._active_tasks["-1001"]
    assert calls["run_sync"]["messages"] == source_messages
    assert calls["run_sync"]["channel_name"] == "Atlas Test"
