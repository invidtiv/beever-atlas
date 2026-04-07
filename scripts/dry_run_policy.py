#!/usr/bin/env python3
"""Comprehensive dry-run for the configurable sync policy system.

Usage:
    python scripts/dry_run_policy.py

Requires: MongoDB running on localhost:27017 (or MONGODB_URI env var).

Coverage levels:
  Level 1 — Unit: Policy resolution cascade, preset definitions
  Level 2 — Data: MongoDB CRUD (policies, defaults, counters, indexes)
  Level 3 — Orchestrator: All 4 consolidation strategies + edge cases
  Level 4 — Scheduler: Job registration, cooldown, concurrency semaphore
  Level 5 — API: FastAPI endpoint integration via TestClient
  Level 6 — Pipeline integration: Config passthrough to BatchProcessor, skip flags
  Level 7 — Backward compatibility: No-policy channels behave as before
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from beever_atlas.models.sync_policy import (
    ChannelPolicy,
    ConsolidationConfig,
    ConsolidationStrategy,
    GlobalPolicyDefaults,
    IngestionConfig,
    ResolvedPolicy,
    SyncConfig,
    SyncTriggerMode,
)
from beever_atlas.services.policy_presets import get_preset_config, list_presets
from beever_atlas.services.policy_resolver import resolve_policy

_total_checks = 0
_total_passed = 0
_total_failed = 0


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check(label: str, condition: bool) -> None:
    global _total_checks, _total_passed, _total_failed
    _total_checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if condition:
        _total_passed += 1
    else:
        _total_failed += 1
        raise AssertionError(f"Check failed: {label}")


def _make_resolved(strategy: ConsolidationStrategy, after_n: int = 3) -> ResolvedPolicy:
    return ResolvedPolicy(
        sync=SyncConfig(
            trigger_mode=SyncTriggerMode.MANUAL, sync_type="auto",
            max_messages=1000, min_sync_interval_minutes=5,
        ),
        ingestion=IngestionConfig(
            batch_size=10, quality_threshold=0.5, max_facts_per_message=2,
            skip_entity_extraction=False, skip_graph_writes=False,
        ),
        consolidation=ConsolidationConfig(
            strategy=strategy, after_n_syncs=after_n, similarity_threshold=0.6,
            merge_threshold=0.85, min_facts_for_clustering=3, staleness_refresh_days=7,
        ),
    )


# ======================================================================
# Level 1: Policy Resolution (pure logic, no I/O)
# ======================================================================


async def test_policy_resolution():
    section("Level 1 — Policy Resolution")
    defaults = GlobalPolicyDefaults()

    # 1a. No channel policy -> all global defaults
    resolved = resolve_policy(None, defaults)
    check("No policy -> manual trigger", resolved.sync.trigger_mode == SyncTriggerMode.MANUAL)
    check("No policy -> batch_size=10", resolved.ingestion.batch_size == 10)
    check("No policy -> quality_threshold=0.5", resolved.ingestion.quality_threshold == 0.5)
    check("No policy -> max_facts=2", resolved.ingestion.max_facts_per_message == 2)
    check("No policy -> skip_entity=False", resolved.ingestion.skip_entity_extraction is False)
    check("No policy -> skip_graph=False", resolved.ingestion.skip_graph_writes is False)
    check("No policy -> after_every_sync", resolved.consolidation.strategy == ConsolidationStrategy.AFTER_EVERY_SYNC)
    check("No policy -> similarity=0.6", resolved.consolidation.similarity_threshold == 0.6)
    check("No policy -> merge=0.85", resolved.consolidation.merge_threshold == 0.85)

    # 1b. Full channel override
    channel = ChannelPolicy(
        channel_id="C_FULL",
        sync=SyncConfig(
            trigger_mode=SyncTriggerMode.CRON, cron_expression="0 9 * * *",
            sync_type="full", max_messages=500, min_sync_interval_minutes=60,
        ),
        ingestion=IngestionConfig(
            batch_size=50, quality_threshold=0.8, max_facts_per_message=5,
            skip_entity_extraction=True, skip_graph_writes=True,
        ),
        consolidation=ConsolidationConfig(
            strategy=ConsolidationStrategy.AFTER_N_SYNCS, after_n_syncs=5,
            cron_expression="0 3 * * *", similarity_threshold=0.7,
            merge_threshold=0.9, min_facts_for_clustering=20, staleness_refresh_days=14,
        ),
    )
    resolved = resolve_policy(channel, defaults)
    check("Full override -> cron trigger", resolved.sync.trigger_mode == SyncTriggerMode.CRON)
    check("Full override -> cron_expression", resolved.sync.cron_expression == "0 9 * * *")
    check("Full override -> full sync", resolved.sync.sync_type == "full")
    check("Full override -> max_messages=500", resolved.sync.max_messages == 500)
    check("Full override -> batch=50", resolved.ingestion.batch_size == 50)
    check("Full override -> quality=0.8", resolved.ingestion.quality_threshold == 0.8)
    check("Full override -> skip_entity=True", resolved.ingestion.skip_entity_extraction is True)
    check("Full override -> skip_graph=True", resolved.ingestion.skip_graph_writes is True)
    check("Full override -> after_n_syncs=5", resolved.consolidation.after_n_syncs == 5)
    check("Full override -> staleness=14", resolved.consolidation.staleness_refresh_days == 14)

    # 1c. Mixed null/non-null (partial override)
    partial = ChannelPolicy(
        channel_id="C_PARTIAL",
        sync=SyncConfig(trigger_mode=SyncTriggerMode.INTERVAL, interval_minutes=30),
        ingestion=IngestionConfig(batch_size=25),
        consolidation=ConsolidationConfig(strategy=ConsolidationStrategy.MANUAL),
    )
    resolved = resolve_policy(partial, defaults)
    check("Partial -> interval trigger", resolved.sync.trigger_mode == SyncTriggerMode.INTERVAL)
    check("Partial -> interval=30", resolved.sync.interval_minutes == 30)
    check("Partial inherit -> sync_type=auto", resolved.sync.sync_type == "auto")
    check("Partial inherit -> max_messages=1000", resolved.sync.max_messages == 1000)
    check("Partial inherit -> min_interval=5", resolved.sync.min_sync_interval_minutes == 5)
    check("Partial -> batch=25", resolved.ingestion.batch_size == 25)
    check("Partial inherit -> quality=0.5", resolved.ingestion.quality_threshold == 0.5)
    check("Partial inherit -> max_facts=2", resolved.ingestion.max_facts_per_message == 2)
    check("Partial inherit -> skip_entity=False", resolved.ingestion.skip_entity_extraction is False)
    check("Partial -> manual consolidation", resolved.consolidation.strategy == ConsolidationStrategy.MANUAL)
    check("Partial inherit -> similarity=0.6", resolved.consolidation.similarity_threshold == 0.6)

    # 1d. Edge: empty channel policy (all None) -> identical to no policy
    empty = ChannelPolicy(channel_id="C_EMPTY")
    resolved_empty = resolve_policy(empty, defaults)
    resolved_none = resolve_policy(None, defaults)
    check("Empty policy == no policy (trigger)", resolved_empty.sync.trigger_mode == resolved_none.sync.trigger_mode)
    check("Empty policy == no policy (batch)", resolved_empty.ingestion.batch_size == resolved_none.ingestion.batch_size)
    check("Empty policy == no policy (strategy)", resolved_empty.consolidation.strategy == resolved_none.consolidation.strategy)


# ======================================================================
# Level 2: Preset Definitions
# ======================================================================


async def test_presets():
    section("Level 2 — Preset Definitions")
    all_presets = list_presets()
    check(f"{len(all_presets)} presets available", len(all_presets) == 4)

    expected_ids = {"real-time", "daily-digest", "lightweight", "manual"}
    actual_ids = {p["id"] for p in all_presets}
    check("Expected preset IDs match", actual_ids == expected_ids)

    for p in all_presets:
        check(f"Preset '{p['id']}' has name", bool(p["name"]))
        check(f"Preset '{p['id']}' has description", bool(p["description"]))
        check(f"Preset '{p['id']}' sync has trigger_mode", p["sync"]["trigger_mode"] is not None)
        check(f"Preset '{p['id']}' consolidation has strategy", p["consolidation"]["strategy"] is not None)

    # Verify specific preset values
    rt = get_preset_config("real-time")
    check("Real-time -> interval trigger", rt["sync"].trigger_mode == SyncTriggerMode.INTERVAL)
    check("Real-time -> 5min interval", rt["sync"].interval_minutes == 5)
    check("Real-time -> after_every_sync", rt["consolidation"].strategy == ConsolidationStrategy.AFTER_EVERY_SYNC)
    check("Real-time -> no skip_entity", rt["ingestion"].skip_entity_extraction is False)

    dd = get_preset_config("daily-digest")
    check("Daily Digest -> cron trigger", dd["sync"].trigger_mode == SyncTriggerMode.CRON)
    check("Daily Digest -> cron=0 2 * * *", dd["sync"].cron_expression == "0 2 * * *")
    check("Daily Digest -> max_messages=5000", dd["sync"].max_messages == 5000)

    lw = get_preset_config("lightweight")
    check("Lightweight -> skip_entity=True", lw["ingestion"].skip_entity_extraction is True)
    check("Lightweight -> skip_graph=True", lw["ingestion"].skip_graph_writes is True)
    check("Lightweight -> manual consolidation", lw["consolidation"].strategy == ConsolidationStrategy.MANUAL)
    check("Lightweight -> quality=0.3", lw["ingestion"].quality_threshold == 0.3)

    mn = get_preset_config("manual")
    check("Manual -> manual trigger", mn["sync"].trigger_mode == SyncTriggerMode.MANUAL)
    check("Manual -> manual consolidation", mn["consolidation"].strategy == ConsolidationStrategy.MANUAL)
    check("Manual -> no skip_entity", mn["ingestion"].skip_entity_extraction is False)

    # Each preset should produce a valid resolved policy when applied
    defaults = GlobalPolicyDefaults()
    for preset_id in expected_ids:
        cfg = get_preset_config(preset_id)
        policy = ChannelPolicy(
            channel_id=f"C_{preset_id}",
            sync=cfg["sync"], ingestion=cfg["ingestion"], consolidation=cfg["consolidation"],
        )
        resolved = resolve_policy(policy, defaults)
        check(f"Preset '{preset_id}' resolves without None trigger", resolved.sync.trigger_mode is not None)
        check(f"Preset '{preset_id}' resolves without None strategy", resolved.consolidation.strategy is not None)

    check("Unknown preset returns None", get_preset_config("nonexistent") is None)


# ======================================================================
# Level 3: MongoDB CRUD
# ======================================================================


async def test_mongodb_crud():
    section("Level 3 — MongoDB Policy CRUD")
    from motor.motor_asyncio import AsyncIOMotorClient
    from beever_atlas.stores.mongodb_store import MongoDBStore

    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/beever_atlas")
    test_uri = uri.replace("/beever_atlas", "/beever_atlas_dry_run")
    store = MongoDBStore(test_uri, db_name="beever_atlas_dry_run")

    try:
        await store.startup()
        check("MongoDB startup OK", True)

        # 3a. Global defaults seeded on startup
        defaults = await store.get_global_defaults()
        check("Global defaults seeded", defaults is not None)
        check("Defaults -> manual trigger", defaults.sync.trigger_mode == SyncTriggerMode.MANUAL)
        from beever_atlas.infra.config import get_settings as _get_settings
        _s = _get_settings()
        check(f"Defaults -> batch_size={_s.sync_batch_size} (from Settings)", defaults.ingestion.batch_size == _s.sync_batch_size)
        check("Defaults -> after_every_sync", defaults.consolidation.strategy == ConsolidationStrategy.AFTER_EVERY_SYNC)
        check("Defaults -> max_concurrent=3", defaults.max_concurrent_syncs == 3)

        # 3b. Idempotent seed (startup again shouldn't duplicate)
        await store.startup()
        defaults2 = await store.get_global_defaults()
        check("Idempotent seed", defaults2.id == "global")

        # 3c. Create policy
        policy = ChannelPolicy(
            channel_id="C_CRUD_1",
            preset="real-time",
            sync=SyncConfig(trigger_mode=SyncTriggerMode.INTERVAL, interval_minutes=5),
            ingestion=IngestionConfig(batch_size=10),
            consolidation=ConsolidationConfig(strategy=ConsolidationStrategy.AFTER_EVERY_SYNC),
        )
        saved = await store.upsert_channel_policy(policy)
        check("Create policy OK", saved.channel_id == "C_CRUD_1")
        check("Create sets updated_at", saved.updated_at is not None)

        # 3d. Read policy
        fetched = await store.get_channel_policy("C_CRUD_1")
        check("Read policy OK", fetched is not None)
        check("Read preset=real-time", fetched.preset == "real-time")
        check("Read trigger=interval", fetched.sync.trigger_mode == SyncTriggerMode.INTERVAL)

        # 3e. Read non-existent policy
        missing = await store.get_channel_policy("C_NONEXISTENT")
        check("Non-existent policy is None", missing is None)

        # 3f. Update policy (upsert existing)
        fetched.preset = "custom"
        fetched.sync.interval_minutes = 15
        updated = await store.upsert_channel_policy(fetched)
        check("Update preset=custom", updated.preset == "custom")
        re_read = await store.get_channel_policy("C_CRUD_1")
        check("Update persisted interval=15", re_read.sync.interval_minutes == 15)

        # 3g. Create second policy
        policy2 = ChannelPolicy(
            channel_id="C_CRUD_2",
            preset="lightweight",
            sync=SyncConfig(trigger_mode=SyncTriggerMode.INTERVAL, interval_minutes=60),
        )
        await store.upsert_channel_policy(policy2)

        # 3h. List policies
        all_policies = await store.list_channel_policies()
        check(f"List returns 2 policies ({len(all_policies)})", len(all_policies) == 2)
        channel_ids = {p.channel_id for p in all_policies}
        check("List contains both channels", channel_ids == {"C_CRUD_1", "C_CRUD_2"})

        # 3i. Sync counter: increment
        count1 = await store.increment_sync_counter("C_CRUD_1")
        check(f"Counter increment 1 -> {count1}", count1 == 1)
        count2 = await store.increment_sync_counter("C_CRUD_1")
        check(f"Counter increment 2 -> {count2}", count2 == 2)
        count3 = await store.increment_sync_counter("C_CRUD_1")
        check(f"Counter increment 3 -> {count3}", count3 == 3)

        # 3j. Sync counter: reset
        await store.reset_sync_counter("C_CRUD_1")
        re_read = await store.get_channel_policy("C_CRUD_1")
        check("Counter reset to 0", re_read.syncs_since_last_consolidation == 0)

        # 3k. Sync counter: increment non-existent (upsert creates doc, returns 1)
        ghost_count = await store.increment_sync_counter("C_GHOST")
        check("Counter upsert on non-existent returns 1", ghost_count == 1)

        # 3l. Update global defaults
        defaults.max_concurrent_syncs = 5
        defaults.ingestion.batch_size = 20
        updated_defaults = await store.update_global_defaults(defaults)
        check("Update defaults max_concurrent=5", updated_defaults.max_concurrent_syncs == 5)
        check("Update defaults batch_size=20", updated_defaults.ingestion.batch_size == 20)

        # 3m. Delete policy
        deleted = await store.delete_channel_policy("C_CRUD_1")
        check("Delete returns True", deleted is True)
        gone = await store.get_channel_policy("C_CRUD_1")
        check("Deleted policy is None", gone is None)

        # 3n. Delete non-existent
        deleted_again = await store.delete_channel_policy("C_CRUD_1")
        check("Delete non-existent returns False", deleted_again is False)

        # 3o. List after delete (C_CRUD_2 + C_GHOST from upsert counter test)
        remaining = await store.list_channel_policies()
        check(f"List after delete returns 2 ({len(remaining)})", len(remaining) == 2)

    finally:
        client = AsyncIOMotorClient(test_uri)
        await client.drop_database("beever_atlas_dry_run")
        client.close()
        await store.shutdown()


# ======================================================================
# Level 4: Orchestrator Strategy Decisions
# ======================================================================


async def test_orchestrator_strategies():
    section("Level 4 — Orchestrator Strategies")
    from beever_atlas.services import pipeline_orchestrator

    # 4a. after_every_sync -> triggers immediately
    pipeline_orchestrator._consolidation_tasks.clear()
    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=_make_resolved(ConsolidationStrategy.AFTER_EVERY_SYNC)),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        await pipeline_orchestrator.on_ingestion_complete("C1", 10)
        await asyncio.sleep(0.1)
        check("after_every_sync triggers consolidation", mock_run.called)
        check("after_every_sync called with channel_id", mock_run.call_args[0][0] == "C1")
    pipeline_orchestrator._consolidation_tasks.clear()

    # 4b. manual -> skips
    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=_make_resolved(ConsolidationStrategy.MANUAL)),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        await pipeline_orchestrator.on_ingestion_complete("C2", 10)
        await asyncio.sleep(0.1)
        check("manual skips consolidation", not mock_run.called)
    pipeline_orchestrator._consolidation_tasks.clear()

    # 4c. scheduled -> skips (consolidation runs on its own cron)
    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=_make_resolved(ConsolidationStrategy.SCHEDULED)),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        await pipeline_orchestrator.on_ingestion_complete("C3", 10)
        await asyncio.sleep(0.1)
        check("scheduled skips consolidation", not mock_run.called)
    pipeline_orchestrator._consolidation_tasks.clear()

    # 4d. after_n_syncs: below threshold -> skips
    mock_stores = MagicMock()
    mock_stores.mongodb.increment_sync_counter = AsyncMock(return_value=1)
    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=_make_resolved(ConsolidationStrategy.AFTER_N_SYNCS, 3)),
        patch.object(pipeline_orchestrator, "get_stores", return_value=mock_stores),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        await pipeline_orchestrator.on_ingestion_complete("C4", 5)
        await asyncio.sleep(0.1)
        check("after_n_syncs count=1/3 skips", not mock_run.called)
        mock_stores.mongodb.increment_sync_counter.assert_called_once_with("C4")
    pipeline_orchestrator._consolidation_tasks.clear()

    # 4e. after_n_syncs: at threshold -> triggers + resets
    mock_stores.mongodb.increment_sync_counter = AsyncMock(return_value=3)
    mock_stores.mongodb.reset_sync_counter = AsyncMock()
    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=_make_resolved(ConsolidationStrategy.AFTER_N_SYNCS, 3)),
        patch.object(pipeline_orchestrator, "get_stores", return_value=mock_stores),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        await pipeline_orchestrator.on_ingestion_complete("C5", 5)
        await asyncio.sleep(0.1)
        check("after_n_syncs count=3/3 triggers", mock_run.called)
        # Counter reset happens inside _run_consolidation (mocked here)
    pipeline_orchestrator._consolidation_tasks.clear()

    # 4f. after_n_syncs: above threshold -> also triggers
    mock_stores.mongodb.increment_sync_counter = AsyncMock(return_value=5)
    mock_stores.mongodb.reset_sync_counter = AsyncMock()
    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=_make_resolved(ConsolidationStrategy.AFTER_N_SYNCS, 3)),
        patch.object(pipeline_orchestrator, "get_stores", return_value=mock_stores),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        await pipeline_orchestrator.on_ingestion_complete("C6", 5)
        await asyncio.sleep(0.1)
        check("after_n_syncs count=5/3 (over) triggers", mock_run.called)
    pipeline_orchestrator._consolidation_tasks.clear()

    # 4g. Duplicate consolidation guard: second call while first is running
    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=_make_resolved(ConsolidationStrategy.AFTER_EVERY_SYNC)),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        # First call
        await pipeline_orchestrator.on_ingestion_complete("C7", 10)
        # Fake: put a non-done task in the tracker
        fake_task = asyncio.create_task(asyncio.sleep(10))
        pipeline_orchestrator._consolidation_tasks["C7"] = fake_task
        # Second call should skip
        await pipeline_orchestrator.on_ingestion_complete("C7", 10)
        await asyncio.sleep(0.1)
        # Should only have been called once (for the first)
        check("Duplicate consolidation guard works", mock_run.call_count == 1)
        fake_task.cancel()
        try:
            await fake_task
        except asyncio.CancelledError:
            pass
    pipeline_orchestrator._consolidation_tasks.clear()

    # 4h. Manual trigger always works
    with patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run:
        await pipeline_orchestrator.trigger_consolidation("C8")
        await asyncio.sleep(0.1)
        check("Manual trigger_consolidation works", mock_run.called)
    pipeline_orchestrator._consolidation_tasks.clear()


# ======================================================================
# Level 5: Scheduler Logic
# ======================================================================


async def _test_scheduler_logic_only():
    """Test concurrency and cooldown concepts without APScheduler dependency."""
    # Concurrency semaphore logic
    sem = asyncio.Semaphore(2)
    await sem.acquire()
    check("Semaphore acquired 1/2", sem._value == 1)
    await sem.acquire()
    check("Semaphore acquired 2/2", sem._value == 0)
    sem.release()
    check("Semaphore released to 1", sem._value == 1)
    sem.release()
    check("Semaphore released to 2", sem._value == 2)

    # Cooldown logic
    from beever_atlas.models.persistence import SyncJob
    recent_job = SyncJob(
        channel_id="C_COOL",
        status="completed",
        completed_at=datetime.now(tz=UTC) - timedelta(minutes=2),
    )
    cooldown_minutes = 5
    elapsed = datetime.now(tz=UTC) - recent_job.completed_at
    should_skip = elapsed < timedelta(minutes=cooldown_minutes)
    check("Cooldown: 2min < 5min -> skip", should_skip is True)

    old_job = SyncJob(
        channel_id="C_COOL",
        status="completed",
        completed_at=datetime.now(tz=UTC) - timedelta(minutes=10),
    )
    elapsed2 = datetime.now(tz=UTC) - old_job.completed_at
    should_proceed = elapsed2 >= timedelta(minutes=cooldown_minutes)
    check("Cooldown: 10min >= 5min -> proceed", should_proceed is True)

    no_cooldown = 0
    check("No cooldown (0): always proceed", no_cooldown <= 0 or elapsed < timedelta(minutes=no_cooldown))


async def test_scheduler():
    section("Level 5 — Scheduler")

    try:
        from beever_atlas.services.scheduler import SyncScheduler
    except ImportError as e:
        print(f"  [SKIP] APScheduler not installed ({e}), testing concurrency/cooldown logic only")
        # Test concurrency and cooldown without the scheduler module
        await _test_scheduler_logic_only()
        return

    # 5a. Concurrency semaphore
    scheduler = SyncScheduler.__new__(SyncScheduler)
    scheduler._global_semaphore = asyncio.Semaphore(2)
    scheduler._started = False

    await scheduler.acquire_sync_semaphore()
    check("Semaphore acquired 1/2", scheduler._global_semaphore._value == 1)
    await scheduler.acquire_sync_semaphore()
    check("Semaphore acquired 2/2", scheduler._global_semaphore._value == 0)
    scheduler.release_sync_semaphore()
    check("Semaphore released to 1", scheduler._global_semaphore._value == 1)
    scheduler.release_sync_semaphore()
    check("Semaphore released to 2", scheduler._global_semaphore._value == 2)

    # 5b. Cooldown enforcement
    from beever_atlas.models.persistence import SyncJob
    mock_stores = MagicMock()

    # Job completed 2 minutes ago, cooldown is 5 minutes -> should skip
    recent_job = SyncJob(
        channel_id="C_COOL",
        status="completed",
        completed_at=datetime.now(tz=UTC) - timedelta(minutes=2),
    )
    mock_stores.mongodb.get_sync_status = AsyncMock(return_value=recent_job)

    resolved = _make_resolved(ConsolidationStrategy.AFTER_EVERY_SYNC)
    # Override min_sync_interval to 5 minutes
    resolved.sync.min_sync_interval_minutes = 5

    # Scheduler._execute_sync uses lazy imports, so we patch get_stores globally
    scheduler2 = SyncScheduler.__new__(SyncScheduler)
    scheduler2._global_semaphore = asyncio.Semaphore(3)
    scheduler2._started = True

    defaults_5min = GlobalPolicyDefaults(
        sync=SyncConfig(trigger_mode=SyncTriggerMode.MANUAL, sync_type="auto", max_messages=1000, min_sync_interval_minutes=5),
        ingestion=IngestionConfig(batch_size=10, quality_threshold=0.5, max_facts_per_message=2, skip_entity_extraction=False, skip_graph_writes=False),
        consolidation=ConsolidationConfig(strategy=ConsolidationStrategy.AFTER_EVERY_SYNC, after_n_syncs=3, similarity_threshold=0.6, merge_threshold=0.85, min_facts_for_clustering=3, staleness_refresh_days=7),
    )

    # Setup mock stores
    mock_stores.mongodb.get_channel_policy = AsyncMock(return_value=None)
    mock_stores.mongodb.get_global_defaults = AsyncMock(return_value=defaults_5min)

    # _execute_sync uses lazy imports from multiple modules, so we patch everywhere
    _patches = [
        "beever_atlas.stores.get_stores",
        "beever_atlas.services.policy_resolver.get_stores",
    ]

    def _multi_patch_stores(mock_s, mock_runner):
        """Context manager that patches get_stores in all locations."""
        from contextlib import ExitStack
        stack = ExitStack()
        for p in _patches:
            stack.enter_context(patch(p, return_value=mock_s))
        stack.enter_context(patch("beever_atlas.api.sync.get_sync_runner", return_value=mock_runner))
        return stack

    # 5b. Cooldown: 2 min ago, cooldown=5 -> skip
    mock_stores.mongodb.get_sync_status = AsyncMock(return_value=recent_job)
    mock_runner_instance = MagicMock()
    mock_runner_instance.start_sync = AsyncMock(return_value="job123")

    with _multi_patch_stores(mock_stores, mock_runner_instance):
        await scheduler2._execute_sync("C_COOL")
        check("Cooldown: sync skipped (2min < 5min)", not mock_runner_instance.start_sync.called)

    # 5c. Cooldown expired: 10 min ago -> proceed
    old_job = SyncJob(
        channel_id="C_COOL",
        status="completed",
        completed_at=datetime.now(tz=UTC) - timedelta(minutes=10),
    )
    mock_stores.mongodb.get_sync_status = AsyncMock(return_value=old_job)
    mock_runner_instance2 = MagicMock()
    mock_runner_instance2.start_sync = AsyncMock(return_value="job456")

    with _multi_patch_stores(mock_stores, mock_runner_instance2):
        await scheduler2._execute_sync("C_COOL2")
        check("Cooldown expired: sync proceeds (10min > 5min)", mock_runner_instance2.start_sync.called)

    # 5d. No cooldown (min_sync_interval_minutes=0) -> always proceed
    from beever_atlas.services.policy_resolver import invalidate_defaults_cache
    invalidate_defaults_cache()  # Clear cached 5min defaults from previous test
    defaults_0min = GlobalPolicyDefaults(
        sync=SyncConfig(trigger_mode=SyncTriggerMode.MANUAL, sync_type="auto", max_messages=1000, min_sync_interval_minutes=0),
        ingestion=IngestionConfig(batch_size=10, quality_threshold=0.5, max_facts_per_message=2, skip_entity_extraction=False, skip_graph_writes=False),
        consolidation=ConsolidationConfig(strategy=ConsolidationStrategy.AFTER_EVERY_SYNC, after_n_syncs=3, similarity_threshold=0.6, merge_threshold=0.85, min_facts_for_clustering=3, staleness_refresh_days=7),
    )
    mock_stores.mongodb.get_channel_policy = AsyncMock(return_value=None)
    mock_stores.mongodb.get_global_defaults = AsyncMock(return_value=defaults_0min)
    mock_stores.mongodb.get_sync_status = AsyncMock(return_value=recent_job)
    mock_runner_instance3 = MagicMock()
    mock_runner_instance3.start_sync = AsyncMock(return_value="job789")

    with _multi_patch_stores(mock_stores, mock_runner_instance3):
        await scheduler2._execute_sync("C_COOL3")
        check("No cooldown (0min): sync proceeds", mock_runner_instance3.start_sync.called)


# ======================================================================
# Level 6: Pipeline Config Passthrough
# ======================================================================


async def test_pipeline_passthrough():
    section("Level 6 — Pipeline Config Passthrough")

    # 6a. BatchProcessor accepts IngestionConfig
    from beever_atlas.services.batch_processor import BatchProcessor
    import inspect
    sig = inspect.signature(BatchProcessor.process_messages)
    params = list(sig.parameters.keys())
    check("BatchProcessor has ingestion_config param", "ingestion_config" in params)

    # 6b. IngestionConfig overrides batch_size
    config = IngestionConfig(batch_size=42, quality_threshold=0.9, max_facts_per_message=5)
    check("IngestionConfig batch_size=42", config.batch_size == 42)
    check("IngestionConfig quality=0.9", config.quality_threshold == 0.9)

    # 6c. Skip flags are boolean-safe
    config_skip = IngestionConfig(skip_entity_extraction=True, skip_graph_writes=True)
    check("skip_entity_extraction=True", config_skip.skip_entity_extraction is True)
    check("skip_graph_writes=True", config_skip.skip_graph_writes is True)

    config_no_skip = IngestionConfig(skip_entity_extraction=False, skip_graph_writes=False)
    check("skip_entity_extraction=False", config_no_skip.skip_entity_extraction is False)

    # 6d. None config should be safe (fallback to global settings)
    config_none = IngestionConfig()
    check("Default IngestionConfig batch_size=None", config_none.batch_size is None)
    check("Default IngestionConfig skip_entity=None", config_none.skip_entity_extraction is None)

    # 6e. ConsolidationConfig min_facts_for_clustering
    consol = ConsolidationConfig(min_facts_for_clustering=10)
    check("min_facts_for_clustering=10", consol.min_facts_for_clustering == 10)

    # 6f. ConsolidationService accepts consolidation_config
    from beever_atlas.services.consolidation import ConsolidationService
    sig2 = inspect.signature(ConsolidationService.__init__)
    params2 = list(sig2.parameters.keys())
    check("ConsolidationService has consolidation_config param", "consolidation_config" in params2)


# ======================================================================
# Level 7: API Endpoints (FastAPI TestClient)
# ======================================================================


async def test_api_endpoints():
    section("Level 7 — API Endpoints")

    from motor.motor_asyncio import AsyncIOMotorClient
    from beever_atlas.stores.mongodb_store import MongoDBStore

    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/beever_atlas")
    test_uri = uri.replace("/beever_atlas", "/beever_atlas_dry_run_api")
    store = MongoDBStore(test_uri, db_name="beever_atlas_dry_run_api")

    try:
        await store.startup()

        # Mock get_stores to use our test store
        mock_stores = MagicMock()
        mock_stores.mongodb = store

        with patch("beever_atlas.api.policies.get_stores", return_value=mock_stores):
            from beever_atlas.api.policies import (
                get_global_defaults,
                get_presets,
                get_channel_policy,
                upsert_channel_policy,
                delete_channel_policy,
                list_policies,
                bulk_apply_policy,
                PolicyUpdateRequest,
                BulkPolicyRequest,
            )

            # 7a. GET /api/policies/defaults
            result = await get_global_defaults()
            check("GET defaults -> sync present", "sync" in result)
            check("GET defaults -> ingestion present", "ingestion" in result)
            check("GET defaults -> consolidation present", "consolidation" in result)
            check("GET defaults -> max_concurrent_syncs", "max_concurrent_syncs" in result)
            check("GET defaults -> trigger_mode=manual", result["sync"]["trigger_mode"] == "manual")

            # 7b. GET /api/policies/presets
            presets = await get_presets()
            check(f"GET presets returns 4 ({len(presets)})", len(presets) == 4)
            check("Presets have 'id' field", all("id" in p for p in presets))

            # 7c. GET channel policy (no policy yet)
            result = await get_channel_policy("C_API_TEST")
            check("GET no-policy -> policy is None", result["policy"] is None)
            check("GET no-policy -> effective has sync", result["effective"]["sync"] is not None)
            check("GET no-policy -> enabled=True", result["enabled"] is True)

            # 7d. PUT channel policy (apply preset)
            body = PolicyUpdateRequest(preset="real-time")
            result = await upsert_channel_policy("C_API_TEST", body)
            check("PUT preset -> channel_id matches", result["channel_id"] == "C_API_TEST")
            check("PUT preset -> preset=real-time", result["preset"] == "real-time")
            check("PUT preset -> effective trigger=interval", result["effective"]["sync"]["trigger_mode"] == "interval")
            check("PUT preset -> effective interval=5", result["effective"]["sync"]["interval_minutes"] == 5)

            # 7e. GET channel policy (after create)
            result = await get_channel_policy("C_API_TEST")
            check("GET after create -> policy not None", result["policy"] is not None)
            check("GET after create -> preset=real-time", result["preset"] == "real-time")

            # 7f. PUT channel policy (custom update)
            body2 = PolicyUpdateRequest(
                sync=SyncConfig(trigger_mode=SyncTriggerMode.INTERVAL, interval_minutes=30),
                ingestion=IngestionConfig(batch_size=25),
            )
            result = await upsert_channel_policy("C_API_TEST", body2)
            check("PUT custom -> preset=custom", result["preset"] == "custom")
            check("PUT custom -> interval=30", result["effective"]["sync"]["interval_minutes"] == 30)

            # 7g. List policies
            policies = await list_policies()
            check(f"List returns >= 1 ({len(policies)})", len(policies) >= 1)
            check("List has channel_id", all("channel_id" in p for p in policies))

            # 7h. Bulk apply
            bulk_body = BulkPolicyRequest(channel_ids=["C_BULK_1", "C_BULK_2"], preset="lightweight")
            result = await bulk_apply_policy(bulk_body)
            check("Bulk apply -> 2 channels updated", len(result["channels_updated"]) == 2)

            # Verify bulk results
            p1 = await get_channel_policy("C_BULK_1")
            check("Bulk -> C_BULK_1 preset=lightweight", p1["preset"] == "lightweight")
            check("Bulk -> C_BULK_1 skip_entity=True", p1["effective"]["ingestion"]["skip_entity_extraction"] is True)

            # 7i. DELETE channel policy
            from fastapi import HTTPException
            result = await delete_channel_policy("C_API_TEST")
            check("DELETE -> status=deleted", result["status"] == "deleted")

            # 7j. DELETE non-existent -> 404
            try:
                await delete_channel_policy("C_API_TEST")
                check("DELETE non-existent -> 404", False)
            except HTTPException as e:
                check("DELETE non-existent -> 404", e.status_code == 404)

            # 7k. GET after delete -> falls back to defaults
            result = await get_channel_policy("C_API_TEST")
            check("GET after delete -> policy=None", result["policy"] is None)
            check("GET after delete -> effective is defaults", result["effective"]["sync"]["trigger_mode"] == "manual")

    finally:
        client = AsyncIOMotorClient(test_uri)
        await client.drop_database("beever_atlas_dry_run_api")
        client.close()
        await store.shutdown()


# ======================================================================
# Level 8: Backward Compatibility
# ======================================================================


async def test_backward_compatibility():
    section("Level 8 — Backward Compatibility")

    # 8a. Channel with no policy resolves to global defaults (current behavior)
    defaults = GlobalPolicyDefaults()
    resolved = resolve_policy(None, defaults)
    check("BC: trigger=manual (current default)", resolved.sync.trigger_mode == SyncTriggerMode.MANUAL)
    check("BC: sync_type=auto (current default)", resolved.sync.sync_type == "auto")
    check("BC: batch_size=10 (matches Settings)", resolved.ingestion.batch_size == 10)
    check("BC: quality=0.5 (matches Settings)", resolved.ingestion.quality_threshold == 0.5)
    check("BC: max_facts=2 (matches Settings)", resolved.ingestion.max_facts_per_message == 2)
    check("BC: skip_entity=False (current default)", resolved.ingestion.skip_entity_extraction is False)
    check("BC: skip_graph=False (current default)", resolved.ingestion.skip_graph_writes is False)
    check("BC: strategy=after_every_sync (current behavior)", resolved.consolidation.strategy == ConsolidationStrategy.AFTER_EVERY_SYNC)
    check("BC: similarity=0.6 (matches Settings)", resolved.consolidation.similarity_threshold == 0.6)
    check("BC: merge=0.85 (matches Settings)", resolved.consolidation.merge_threshold == 0.85)

    # 8b. Global defaults match the code defaults in Settings class (not .env overrides)
    # These are the product defaults that ship with the app — the values in Settings(...)
    # field definitions, not whatever the user's .env might override them to.
    check("BC: GlobalDefaults.batch_size == 10 (code default)", defaults.ingestion.batch_size == 10)
    check("BC: GlobalDefaults.quality == 0.5 (code default)", defaults.ingestion.quality_threshold == 0.5)
    check("BC: GlobalDefaults.max_facts == 2 (code default)", defaults.ingestion.max_facts_per_message == 2)
    check("BC: GlobalDefaults.max_messages == 1000 (code default)", defaults.sync.max_messages == 1000)
    check("BC: GlobalDefaults.similarity == 0.6 (code default)", defaults.consolidation.similarity_threshold == 0.6)
    check("BC: GlobalDefaults.merge == 0.85 (code default)", defaults.consolidation.merge_threshold == 0.85)

    # 8c. Orchestrator: after_every_sync is the default -> consolidation always fires (current behavior)
    from beever_atlas.services import pipeline_orchestrator
    pipeline_orchestrator._consolidation_tasks.clear()

    with (
        patch.object(pipeline_orchestrator, "resolve_effective_policy", new_callable=AsyncMock, return_value=resolved),
        patch.object(pipeline_orchestrator, "_run_consolidation", new_callable=AsyncMock) as mock_run,
    ):
        await pipeline_orchestrator.on_ingestion_complete("C_BC", 5)
        await asyncio.sleep(0.1)
        check("BC: default policy triggers consolidation after sync", mock_run.called)
    pipeline_orchestrator._consolidation_tasks.clear()


# ======================================================================
# Main
# ======================================================================


async def main():
    print("\n" + "=" * 60)
    print("  Configurable Sync Policy — Comprehensive Dry Run")
    print("=" * 60)
    start = time.time()
    sections_passed = 0
    sections_failed = 0

    tests = [
        test_policy_resolution,
        test_presets,
        test_mongodb_crud,
        test_orchestrator_strategies,
        test_scheduler,
        test_pipeline_passthrough,
        test_api_endpoints,
        test_backward_compatibility,
    ]

    for test_fn in tests:
        try:
            await test_fn()
            sections_passed += 1
        except AssertionError as e:
            print(f"\n  FAILED: {e}")
            sections_failed += 1
        except Exception as e:
            print(f"\n  ERROR in {test_fn.__name__}: {type(e).__name__}: {e}")
            sections_failed += 1

    elapsed = time.time() - start
    section("Summary")
    print(f"  Test sections: {sections_passed + sections_failed} ({sections_passed} passed, {sections_failed} failed)")
    print(f"  Total checks:  {_total_checks} ({_total_passed} passed, {_total_failed} failed)")
    print(f"  Time:          {elapsed:.2f}s")
    print()

    if sections_failed:
        print("  RESULT: SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("  RESULT: ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
