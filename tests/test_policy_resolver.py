"""Unit tests for policy resolution cascade."""

from beever_atlas.models.sync_policy import (
    ChannelPolicy,
    ConsolidationConfig,
    ConsolidationStrategy,
    GlobalPolicyDefaults,
    IngestionConfig,
    SyncConfig,
    SyncTriggerMode,
)
from beever_atlas.services.policy_resolver import resolve_policy


def _defaults() -> GlobalPolicyDefaults:
    return GlobalPolicyDefaults()


def test_no_channel_policy_returns_global_defaults():
    defaults = _defaults()
    resolved = resolve_policy(None, defaults)

    assert resolved.sync.trigger_mode == SyncTriggerMode.MANUAL
    assert resolved.ingestion.batch_size == 10
    assert resolved.ingestion.quality_threshold == 0.5
    assert resolved.consolidation.strategy == ConsolidationStrategy.AFTER_EVERY_SYNC


def test_all_channel_fields_override_defaults():
    defaults = _defaults()
    channel = ChannelPolicy(
        channel_id="C123",
        sync=SyncConfig(
            trigger_mode=SyncTriggerMode.INTERVAL,
            interval_minutes=15,
            sync_type="full",
            max_messages=500,
            min_sync_interval_minutes=10,
        ),
        ingestion=IngestionConfig(
            batch_size=50,
            quality_threshold=0.8,
            max_facts_per_message=5,
            skip_entity_extraction=True,
            skip_graph_writes=True,
        ),
        consolidation=ConsolidationConfig(
            strategy=ConsolidationStrategy.AFTER_N_SYNCS,
            after_n_syncs=5,
            similarity_threshold=0.7,
            merge_threshold=0.9,
            min_facts_for_clustering=20,
            staleness_refresh_days=14,
        ),
    )
    resolved = resolve_policy(channel, defaults)

    assert resolved.sync.trigger_mode == SyncTriggerMode.INTERVAL
    assert resolved.sync.interval_minutes == 15
    assert resolved.sync.sync_type == "full"
    assert resolved.sync.max_messages == 500
    assert resolved.ingestion.batch_size == 50
    assert resolved.ingestion.quality_threshold == 0.8
    assert resolved.ingestion.skip_entity_extraction is True
    assert resolved.consolidation.strategy == ConsolidationStrategy.AFTER_N_SYNCS
    assert resolved.consolidation.after_n_syncs == 5
    assert resolved.consolidation.similarity_threshold == 0.7


def test_mixed_null_and_nonnull_fields():
    defaults = _defaults()
    channel = ChannelPolicy(
        channel_id="C456",
        sync=SyncConfig(
            trigger_mode=SyncTriggerMode.CRON,
            cron_expression="0 9 * * *",
            # sync_type, max_messages, min_sync_interval_minutes are None -> inherit
        ),
        ingestion=IngestionConfig(
            batch_size=50,
            # quality_threshold is None -> inherit 0.5
            skip_entity_extraction=True,
            # skip_graph_writes is None -> inherit False
        ),
        consolidation=ConsolidationConfig(
            strategy=ConsolidationStrategy.MANUAL,
            # all thresholds None -> inherit
        ),
    )
    resolved = resolve_policy(channel, defaults)

    # Channel values
    assert resolved.sync.trigger_mode == SyncTriggerMode.CRON
    assert resolved.sync.cron_expression == "0 9 * * *"
    assert resolved.ingestion.batch_size == 50
    assert resolved.ingestion.skip_entity_extraction is True
    assert resolved.consolidation.strategy == ConsolidationStrategy.MANUAL

    # Global defaults inherited
    assert resolved.sync.sync_type == "auto"
    assert resolved.sync.max_messages == 1000
    assert resolved.sync.min_sync_interval_minutes == 5
    assert resolved.ingestion.quality_threshold == 0.5
    assert resolved.ingestion.skip_graph_writes is False
    assert resolved.consolidation.similarity_threshold == 0.6
    assert resolved.consolidation.merge_threshold == 0.85
    assert resolved.consolidation.min_facts_for_clustering == 3
