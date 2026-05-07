/**
 * ExtractionWorkerPanel
 *
 * Replaces the legacy "Syncing channel · X of Y batches · Initializing..."
 * widget when DECOUPLE_EXTRACTION=true is in effect. Detects decoupled mode
 * by checking that extraction-status shows pending+extracting > 0 while
 * the sync job itself has zero batch_results (sync returned immediately after
 * upserting messages — no inline batches were processed).
 *
 * Layout:
 *   1. Header — current stage + breaker badge + collapse toggle
 *   2. Stacked progress bar with done/pct + ETA
 *   3. Four count chips (done / in progress / pending / failed)
 *   4. Wiki maintainer activity row (only when wiki rewrites > 0)
 *   5. (collapsible) Throughput trend (5/15/60 min) + recent failures feed +
 *      wiki rewrites-by-kind breakdown
 */

import { useMemo, useState } from "react";
import {
  Loader2,
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileText,
  Sparkles,
  Hourglass,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ExtractionStatusResponse } from "@/hooks/useExtractionStatus";
import type {
  ExtractionWorkerMetrics,
  WikiMaintainerMetrics,
} from "@/hooks/useExtractionWorkerMetrics";
import { useExtractionWorkerMetrics } from "@/hooks/useExtractionWorkerMetrics";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExtractionWorkerPanelProps {
  /** Channel to monitor. Must be provided; the panel renders null if absent. */
  channelId: string;
  /** Latest extraction-status counts from the polling hook. */
  extractionStatus: ExtractionStatusResponse | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtRate(rate: number | null | undefined): string {
  if (rate == null || !Number.isFinite(rate)) return "—";
  if (rate >= 10) return `${rate.toFixed(0)}/min`;
  if (rate >= 1) return `${rate.toFixed(1)}/min`;
  return `${(rate * 60).toFixed(1)}/min`;
}

/** Compute a human-readable ETA for the remaining queue.
 *
 *  Uses ``claim_rate_5min`` (claims per minute) so the estimate reflects
 *  current throughput, not a historical average. Returns ``null`` when
 *  the rate is unknown / zero / nonsensical, leaving the caller to render
 *  a neutral "calculating" state.
 */
function estimateEta(
  remaining: number,
  claimRatePerMin: number | null | undefined,
): string | null {
  if (remaining <= 0) return null;
  if (!claimRatePerMin || claimRatePerMin <= 0) return null;
  const minutes = remaining / claimRatePerMin;
  if (minutes < 0.5) return "<30s";
  if (minutes < 1) return "<1 min";
  if (minutes < 60) return `~${Math.round(minutes)} min`;
  const hours = minutes / 60;
  if (hours < 24) return `~${hours.toFixed(1)}h`;
  return `~${(hours / 24).toFixed(1)}d`;
}

function totalWikiRewrites(
  byKind: Record<string, number> | null | undefined,
): number {
  if (!byKind) return 0;
  return Object.values(byKind).reduce((a, b) => a + b, 0);
}

function totalPendingDirty(
  perChannel: Record<string, number> | null | undefined,
): number {
  if (!perChannel) return 0;
  return Object.values(perChannel).reduce((a, b) => a + b, 0);
}

/** Per-channel queue depth filtered to the current channel. Falls back
 *  to the cross-channel sum when the per-channel breakdown is empty so
 *  the user always sees a meaningful number. */
function channelQueueDepth(
  perChannel: Record<string, number> | null | undefined,
  channelId: string,
): number | null {
  if (!perChannel) return null;
  if (channelId in perChannel) return perChannel[channelId];
  return null;
}

// ---------------------------------------------------------------------------
// BreakerBadge
// ---------------------------------------------------------------------------

interface BreakerBadgeProps {
  state: string | null | undefined;
}

function BreakerBadge({ state }: BreakerBadgeProps) {
  if (!state) return null;

  const lower = state.toLowerCase();
  const isClosed = lower === "closed";
  const isHalf = lower === "half_open";
  const isOpen = lower === "open";

  return (
    <span
      data-testid="breaker-badge"
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border",
        isClosed
          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
          : isHalf
            ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
            : isOpen
              ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
              : "bg-muted text-muted-foreground border-border",
      )}
    >
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          isClosed
            ? "bg-emerald-500"
            : isHalf
              ? "bg-amber-500 animate-pulse"
              : isOpen
                ? "bg-red-500 animate-pulse"
                : "bg-muted-foreground/40",
        )}
      />
      {isClosed ? "healthy" : isHalf ? "recovering" : isOpen ? "open" : state}
    </span>
  );
}

// ---------------------------------------------------------------------------
// StackedBar
// ---------------------------------------------------------------------------

interface StackedBarProps {
  done: number;
  extracting: number;
  pending: number;
  failed: number;
  total: number;
}

function StackedBar({ done, extracting, pending, failed, total }: StackedBarProps) {
  if (total === 0) return null;

  const donePct = (done / total) * 100;
  const extractingPct = (extracting / total) * 100;
  const failedPct = (failed / total) * 100;

  return (
    <div
      data-testid="stacked-bar"
      className="h-2 w-full rounded-full bg-muted overflow-hidden flex"
      role="progressbar"
      aria-valuenow={done}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label={`${done} of ${total} messages extracted`}
    >
      <div
        className="h-full bg-emerald-500 transition-all duration-700 ease-out"
        style={{ width: `${donePct}%` }}
      />
      <div
        className="h-full bg-primary animate-pulse transition-all duration-700 ease-out"
        style={{ width: `${extractingPct}%` }}
      />
      <div
        className="h-full bg-red-500/70 transition-all duration-700 ease-out"
        style={{ width: `${failedPct}%` }}
      />
      {/* pending fills the rest implicitly through bg-muted */}
      {pending > 0 && (
        <div
          className="h-full bg-muted-foreground/10"
          style={{ width: `${(pending / total) * 100}%` }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CountChip
// ---------------------------------------------------------------------------

interface CountChipProps {
  label: string;
  value: number;
  variant: "done" | "active" | "pending" | "failed";
  testId?: string;
}

function CountChip({ label, value, variant, testId }: CountChipProps) {
  const cls = {
    done: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
    active: "bg-primary/10 text-primary border-primary/20",
    pending: "bg-muted text-muted-foreground border-border",
    failed: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
  }[variant];

  return (
    <span
      data-testid={testId}
      className={cn(
        "inline-flex flex-col items-center rounded-lg border px-2.5 py-1.5 min-w-[52px]",
        cls,
      )}
    >
      <span className="text-base font-semibold leading-none">{value}</span>
      <span className="text-[10px] mt-0.5 font-normal opacity-80">{label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// StageLabel — describes WHAT the worker is doing right now in plain English
// ---------------------------------------------------------------------------

interface StageLabelProps {
  pending: number;
  extracting: number;
  done: number;
  failed: number;
  total: number;
  breakerState: string | null | undefined;
}

function StageLabel({
  pending,
  extracting,
  done,
  failed,
  total,
  breakerState,
}: StageLabelProps) {
  // Order matters — most informative state wins.
  if (breakerState && breakerState.toLowerCase() === "open") {
    return {
      icon: AlertTriangle,
      iconClass: "text-red-500",
      text: "Paused — LLM provider unavailable",
      subtext: "Retrying automatically",
    };
  }
  if (extracting > 0) {
    return {
      icon: Loader2,
      iconClass: "text-primary animate-spin",
      text: `Extracting facts from ${extracting} message${extracting === 1 ? "" : "s"}`,
      subtext:
        pending > 0
          ? `${pending} more queued`
          : "Wrapping up the queue",
    };
  }
  if (pending > 0) {
    return {
      icon: Hourglass,
      iconClass: "text-muted-foreground",
      text: `${pending} message${pending === 1 ? "" : "s"} queued for extraction`,
      subtext: "Worker will claim within 30 s",
    };
  }
  if (total > 0 && done === total - failed) {
    return {
      icon: CheckCircle2,
      iconClass: "text-emerald-500",
      text: failed > 0 ? "Extraction complete (with failures)" : "Extraction complete",
      subtext:
        failed > 0
          ? `${failed} message${failed === 1 ? "" : "s"} failed — see details`
          : `${done} fact${done === 1 ? "" : "s"} ready`,
    };
  }
  return {
    icon: Loader2,
    iconClass: "animate-spin text-primary",
    text: "Extraction worker",
    subtext: "Polling Mongo for new messages",
  };
}

// ---------------------------------------------------------------------------
// FailureRow
// ---------------------------------------------------------------------------

interface FailureRowProps {
  failure: { message_id: string; channel_id: string; error_class: string };
  highlight: boolean;
}

function FailureRow({ failure, highlight }: FailureRowProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md border px-2 py-1 text-[10px]",
        highlight
          ? "border-red-500/30 bg-red-500/5"
          : "border-border bg-card/50",
      )}
    >
      <XCircle size={10} className="shrink-0 text-red-500" />
      <span className="font-medium text-red-700 dark:text-red-400">
        {failure.error_class}
      </span>
      <span className="text-muted-foreground/60 font-mono ml-auto">
        msg #{failure.message_id.slice(-8)}
      </span>
      {failure.channel_id && !highlight && (
        <span className="text-muted-foreground/60 font-mono">
          ch #{failure.channel_id.slice(-6)}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inner panel (accepts pre-fetched metrics for testability)
// ---------------------------------------------------------------------------

interface InnerPanelProps {
  channelId: string;
  extractionStatus: ExtractionStatusResponse;
  workerMetrics: ExtractionWorkerMetrics | null;
  wikiMetrics: WikiMaintainerMetrics | null;
}

export function ExtractionWorkerPanelInner({
  channelId,
  extractionStatus,
  workerMetrics,
  wikiMetrics,
}: InnerPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const { counts, total } = extractionStatus;
  const { pending, extracting, done, failed } = counts;

  const claimRate = workerMetrics?.claim_rate_5min ?? null;
  const breakerState = workerMetrics?.breaker_state ?? null;

  const wikiRewrites = totalWikiRewrites(wikiMetrics?.rewrite_count_by_page_kind);
  const wikiPendingDirty = totalPendingDirty(wikiMetrics?.pending_dirty_pages_per_channel);
  const applyUpdates = wikiMetrics?.apply_update_count_5min ?? 0;
  const wikiActive = wikiRewrites > 0 || applyUpdates > 0 || wikiPendingDirty > 0;

  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  // ETA derived from the same claim rate we display in the throughput row.
  // Hidden when nothing is queued (the "Complete" stage label takes over).
  const eta = useMemo(
    () => estimateEta(pending + extracting, claimRate),
    [pending, extracting, claimRate],
  );

  // Stage label: the single-line "what's happening" status.
  const stage = StageLabel({
    pending,
    extracting,
    done,
    failed,
    total,
    breakerState,
  });
  const StageIcon = stage.icon;

  // Channel-scoped indicators: queue depth + dirty wiki pages for THIS
  // channel, so the panel is meaningful on a per-channel page even when
  // the global metrics include other channels.
  const channelQueue = channelQueueDepth(
    workerMetrics?.queue_depth_per_channel,
    channelId,
  );
  const channelDirty = channelQueueDepth(
    wikiMetrics?.pending_dirty_pages_per_channel,
    channelId,
  );

  // Channel-scoped failures get a red border in the recent-failures feed.
  const recentFailures = workerMetrics?.recent_failures ?? [];

  return (
    <div
      data-testid="extraction-worker-panel"
      className="rounded-xl border border-white/10 bg-card/70 backdrop-blur px-4 py-3 space-y-3"
    >
      {/* Header — stage + breaker + expand toggle */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 min-w-0 flex-1">
          <StageIcon size={14} className={cn("mt-0.5 shrink-0", stage.iconClass)} />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-foreground truncate">
              {stage.text}
            </div>
            <div className="text-[11px] text-muted-foreground truncate">
              {stage.subtext}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <BreakerBadge state={breakerState} />
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-0.5 rounded px-1.5 py-1 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            aria-label={expanded ? "Collapse details" : "Expand details"}
            aria-expanded={expanded}
          >
            {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {expanded ? "Less" : "Details"}
          </button>
        </div>
      </div>

      {/* Progress bar with ETA inline */}
      <div className="space-y-1">
        <StackedBar
          done={done}
          extracting={extracting}
          pending={pending}
          failed={failed}
          total={total}
        />
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span>
            {done}/{total} ({pct}%)
          </span>
          <div className="flex items-center gap-3">
            {claimRate != null && (
              <span className="flex items-center gap-1">
                <Zap size={9} />
                {fmtRate(claimRate)}
              </span>
            )}
            {eta != null && (
              <span className="flex items-center gap-1 text-foreground font-medium">
                <Clock size={9} />
                {eta} remaining
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Count chips */}
      <div
        data-testid="count-chips"
        className="flex items-start gap-2 flex-wrap"
      >
        <CountChip
          label="done"
          value={done}
          variant="done"
          testId="chip-done"
        />
        <CountChip
          label="in progress"
          value={extracting}
          variant="active"
          testId="chip-extracting"
        />
        <CountChip
          label="pending"
          value={pending}
          variant="pending"
          testId="chip-pending"
        />
        <CountChip
          label="failed"
          value={failed}
          variant="failed"
          testId="chip-failed"
        />
      </div>

      {/* Wiki activity row — visible compact when active */}
      {wikiActive && (
        <div className="rounded-md border border-violet-500/20 bg-violet-500/5 px-3 py-1.5 flex items-start gap-2">
          <Sparkles size={11} className="mt-0.5 text-violet-500 shrink-0" />
          <div className="text-[11px] text-violet-800 dark:text-violet-200 leading-relaxed">
            {applyUpdates > 0 && (
              <>
                <span className="font-semibold">{applyUpdates}</span> facts
                integrated into wiki
              </>
            )}
            {applyUpdates > 0 && wikiRewrites > 0 && " · "}
            {wikiRewrites > 0 && (
              <>
                <span className="font-semibold">{wikiRewrites}</span> page
                {wikiRewrites === 1 ? "" : "s"} rewritten
              </>
            )}
            {(applyUpdates > 0 || wikiRewrites > 0) && wikiPendingDirty > 0 && " · "}
            {wikiPendingDirty > 0 && (
              <span className="text-violet-600/70 dark:text-violet-400/70">
                {wikiPendingDirty} page{wikiPendingDirty === 1 ? "" : "s"} dirty
              </span>
            )}
          </div>
        </div>
      )}

      {/* Expanded details — throughput trend + recent failures + wiki kinds */}
      {expanded && (
        <div className="border-t border-border/50 pt-3 space-y-3">
          {/* Throughput trend table */}
          {workerMetrics && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70 font-medium mb-1.5">
                Worker throughput
              </div>
              <div className="grid grid-cols-3 gap-2">
                <ThroughputCell label="5 min" value={workerMetrics.claim_rate_5min} />
                <ThroughputCell label="15 min" value={workerMetrics.claim_rate_15min} />
                <ThroughputCell label="60 min" value={workerMetrics.claim_rate_60min} />
              </div>
              {workerMetrics.success_rate_5min < 1 && (
                <div className="mt-2 flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400">
                  <AlertTriangle size={11} />
                  {Math.round(workerMetrics.success_rate_5min * 100)}% success
                  rate over the last 5 minutes
                </div>
              )}
            </div>
          )}

          {/* Channel-scoped depth + dirty pages */}
          {(channelQueue !== null || channelDirty !== null) && (
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              {channelQueue !== null && (
                <div className="rounded-md border border-border bg-card/50 px-2 py-1.5">
                  <div className="text-muted-foreground text-[10px]">
                    Queue (this channel)
                  </div>
                  <div className="text-foreground font-semibold">
                    {channelQueue}
                  </div>
                </div>
              )}
              {channelDirty !== null && (
                <div className="rounded-md border border-border bg-card/50 px-2 py-1.5">
                  <div className="text-muted-foreground text-[10px]">
                    Dirty wiki pages
                  </div>
                  <div className="text-foreground font-semibold">
                    {channelDirty}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Recent failures — full list (up to 5) when expanded */}
          {recentFailures.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70 font-medium mb-1.5">
                Recent failures ({recentFailures.length})
              </div>
              <div className="space-y-1 max-h-[120px] overflow-y-auto">
                {recentFailures.slice(0, 5).map((f, i) => (
                  <FailureRow
                    key={`${f.message_id}-${i}`}
                    failure={f}
                    highlight={f.channel_id === channelId}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Wiki rewrites by page kind */}
          {wikiMetrics?.rewrite_count_by_page_kind &&
            Object.keys(wikiMetrics.rewrite_count_by_page_kind).length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground/70 font-medium mb-1.5">
                  Wiki rewrites by kind
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(wikiMetrics.rewrite_count_by_page_kind)
                    .sort(([, a], [, b]) => b - a)
                    .map(([kind, count]) => (
                      <span
                        key={kind}
                        className="inline-flex items-center gap-1 rounded-md border border-violet-500/20 bg-violet-500/5 px-1.5 py-0.5 text-[10px] text-violet-700 dark:text-violet-300"
                      >
                        <FileText size={9} />
                        <span className="font-medium">{kind}</span>
                        <span className="opacity-70">×{count}</span>
                      </span>
                    ))}
                </div>
              </div>
            )}

          {wikiMetrics &&
            wikiMetrics.apply_update_failures > 0 && (
              <div className="flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400">
                <AlertTriangle size={11} />
                {wikiMetrics.apply_update_failures} wiki update
                {wikiMetrics.apply_update_failures === 1 ? "" : "s"} failed in
                the last 5 minutes
              </div>
            )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ThroughputCell
// ---------------------------------------------------------------------------

function ThroughputCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-card/50 px-2 py-1.5">
      <div className="text-muted-foreground text-[10px]">{label}</div>
      <div className="text-foreground font-semibold text-xs">
        {fmtRate(value)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public component (owns the metrics-fetching lifecycle)
// ---------------------------------------------------------------------------

export function ExtractionWorkerPanel({
  channelId,
  extractionStatus,
}: ExtractionWorkerPanelProps) {
  const isActive =
    extractionStatus !== null &&
    ((extractionStatus.counts.pending ?? 0) > 0 ||
      (extractionStatus.counts.extracting ?? 0) > 0);

  const { workerMetrics, wikiMetrics } = useExtractionWorkerMetrics({
    isActive,
    pollMsActive: 4000,
    pollMsIdle: 0,
  });

  if (!channelId || !extractionStatus) return null;

  return (
    <ExtractionWorkerPanelInner
      channelId={channelId}
      extractionStatus={extractionStatus}
      workerMetrics={workerMetrics}
      wikiMetrics={wikiMetrics}
    />
  );
}
