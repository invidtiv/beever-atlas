import type { PolicyPreset } from "./types";

export const POLICY_PRESETS: PolicyPreset[] = [
  {
    id: "real-time",
    name: "Real-time",
    description: "Updates every 5 minutes with full extraction and auto-organization.",
    sync: { trigger_mode: "interval", interval_minutes: 5, cron_expression: null, sync_type: "auto", max_messages: 1000, min_sync_interval_minutes: 3 },
    ingestion: { batch_size: 10, quality_threshold: 0.5, max_facts_per_message: 2, skip_entity_extraction: false, skip_graph_writes: false },
    consolidation: { strategy: "after_every_sync", after_n_syncs: null, cron_expression: null, similarity_threshold: 0.6, merge_threshold: 0.85, min_facts_for_clustering: 3, staleness_refresh_days: null },
    wiki: { enabled: true, generation_strategy: "after_consolidation", cron_expression: null, auto_regenerate_on_stale: true, min_facts_for_generation: 10, topic_subpage_threshold: 5 },
  },
  {
    id: "daily-digest",
    name: "Daily Digest",
    description: "Syncs once a day at 2 AM with full extraction and auto-organization.",
    sync: { trigger_mode: "cron", cron_expression: "0 2 * * *", interval_minutes: null, sync_type: "auto", max_messages: 5000, min_sync_interval_minutes: 60 },
    ingestion: { batch_size: 20, quality_threshold: 0.5, max_facts_per_message: 3, skip_entity_extraction: false, skip_graph_writes: false },
    consolidation: { strategy: "after_every_sync", after_n_syncs: null, cron_expression: null, similarity_threshold: 0.6, merge_threshold: 0.85, min_facts_for_clustering: 5, staleness_refresh_days: null },
    wiki: { enabled: true, generation_strategy: "after_consolidation", cron_expression: null, auto_regenerate_on_stale: true, min_facts_for_generation: 15, topic_subpage_threshold: 5 },
  },
  {
    id: "lightweight",
    name: "Lightweight",
    description: "Syncs every hour with quick extraction. Organize knowledge manually.",
    sync: { trigger_mode: "interval", interval_minutes: 60, cron_expression: null, sync_type: "auto", max_messages: 500, min_sync_interval_minutes: 30 },
    ingestion: { batch_size: 15, quality_threshold: 0.3, max_facts_per_message: 2, skip_entity_extraction: true, skip_graph_writes: true },
    consolidation: { strategy: "manual", after_n_syncs: null, cron_expression: null, similarity_threshold: 0.5, merge_threshold: 0.8, min_facts_for_clustering: 10, staleness_refresh_days: null },
    wiki: { enabled: false, generation_strategy: "manual", cron_expression: null, auto_regenerate_on_stale: false, min_facts_for_generation: 20, topic_subpage_threshold: 8 },
  },
  {
    id: "manual",
    name: "Manual",
    description: "Full control — sync and organize only when you choose.",
    sync: { trigger_mode: "manual", interval_minutes: null, cron_expression: null, sync_type: "auto", max_messages: 1000, min_sync_interval_minutes: 1 },
    ingestion: { batch_size: 10, quality_threshold: 0.5, max_facts_per_message: 2, skip_entity_extraction: false, skip_graph_writes: false },
    consolidation: { strategy: "manual", after_n_syncs: null, cron_expression: null, similarity_threshold: 0.6, merge_threshold: 0.85, min_facts_for_clustering: 3, staleness_refresh_days: null },
    wiki: { enabled: false, generation_strategy: "manual", cron_expression: null, auto_regenerate_on_stale: false, min_facts_for_generation: 10, topic_subpage_threshold: 5 },
  },
];
