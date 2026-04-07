import { useState } from "react";
import { useParams } from "react-router-dom";
import { RefreshCw, Sparkles } from "lucide-react";
import { useMemories } from "@/hooks/useMemories";
import { useTopics } from "@/hooks/useTopics";
import { useChannelSummary } from "@/hooks/useChannelSummary";
import { api, ApiError } from "@/lib/api";
import { MemoryFilters } from "./MemoryFilters";
import { FactCard } from "./FactCard";
import { SummaryCard } from "./SummaryCard";
import { ClusterCard } from "./ClusterCard";

export function TierBrowser() {
  const { id } = useParams<{ id: string }>();
  const channelId = id ?? "";
  const { facts, filters, setFilters, isLoading } = useMemories(channelId);
  const { clusters, isLoading: clustersLoading, error: clustersError, refetch: refetchTopics } = useTopics(channelId);
  const { summary, isLoading: summaryLoading, error: summaryError, refetch: refetchSummary } = useChannelSummary(channelId);

  const [consolidating, setConsolidating] = useState(false);
  const [showRefresh, setShowRefresh] = useState(false);
  const [consolidateMsg, setConsolidateMsg] = useState("");

  const handleConsolidate = async () => {
    setConsolidating(true);
    setConsolidateMsg("");
    try {
      await api.post(`/api/channels/${channelId}/consolidate`);
      setConsolidateMsg("Consolidation started. Refresh in a few minutes to see updated results.");
      setShowRefresh(true);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to start consolidation";
      setConsolidateMsg(msg);
    } finally {
      setConsolidating(false);
    }
  };

  const handleRefresh = () => {
    refetchTopics();
    refetchSummary();
    setShowRefresh(false);
    setConsolidateMsg("");
  };

  if (isLoading && summaryLoading && clustersLoading) {
    return (
      <div className="p-6 text-center text-base text-muted-foreground">
        Loading memories...
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-5 animate-fade-in max-w-6xl mx-auto">
      {/* Actions bar */}
      <div className="flex items-center justify-end gap-2">
        {showRefresh && (
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-primary/30 text-primary hover:bg-primary/10 transition-colors"
          >
            <RefreshCw size={14} />
            Refresh results
          </button>
        )}
        <button
          onClick={handleConsolidate}
          disabled={consolidating || !channelId}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-border text-muted-foreground hover:bg-muted/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Sparkles size={14} />
          {consolidating ? "Starting..." : "Reconsolidate"}
        </button>
      </div>

      {consolidateMsg && (
        <div className="rounded-lg border border-border bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground">
          {consolidateMsg}
        </div>
      )}

      {/* Tier 0 — Channel Summary */}
      {summaryLoading ? (
        <div className="rounded-xl border border-border bg-card px-5 py-4 text-sm text-muted-foreground animate-pulse">
          Loading channel summary...
        </div>
      ) : summaryError ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-4 text-sm text-destructive">
          Failed to load channel summary.
        </div>
      ) : summary ? (
        <SummaryCard summary={summary} />
      ) : (
        <div className="rounded-xl border border-dashed border-border px-5 py-4 text-sm text-muted-foreground">
          No channel summary yet. Run consolidation to generate one.
        </div>
      )}

      {/* Tier 1 — Topic Clusters */}
      <div className="space-y-3">
        <div className="flex items-end justify-between">
          <div>
            <h3 className="font-heading text-[28px] leading-tight text-foreground">
              Topics
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Knowledge organized by topic.
            </p>
          </div>
          {clusters.length > 0 && (
            <span className="text-sm text-muted-foreground">
              {clusters.length} topics
            </span>
          )}
        </div>

        {clustersLoading ? (
          <div className="rounded-xl border border-border bg-card px-5 py-4 text-sm text-muted-foreground animate-pulse">
            Loading topic clusters...
          </div>
        ) : clustersError ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-4 text-sm text-destructive">
            Failed to load topic clusters.
          </div>
        ) : clusters.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-5 py-4 text-sm text-muted-foreground">
            No topic clusters yet. Sync and consolidate to organize knowledge.
          </div>
        ) : (
          <div className="space-y-3">
            {clusters.map((c, idx) => (
              <div
                key={c.id}
                className="motion-safe:animate-rise-in"
                style={{ animationDelay: `${Math.min(idx, 10) * 35}ms` }}
              >
                <ClusterCard cluster={c} facts={facts} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tier 2 — Atomic facts */}
      <div className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="font-heading text-[28px] leading-tight text-foreground">
              Atomic Facts
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Individual knowledge extracted from this channel.
            </p>
          </div>
          <span className="text-sm text-muted-foreground">
            {facts.length} matching facts
          </span>
        </div>

        <MemoryFilters filters={filters} setFilters={setFilters} />

        {facts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-5 py-10 text-center text-sm text-muted-foreground">
            No memories yet. Sync this channel to start extracting knowledge.
          </div>
        ) : (
          <div className="space-y-3">
            {facts.map((fact, idx) => (
              <div
                key={fact.id}
                className="motion-safe:animate-rise-in"
                style={{ animationDelay: `${Math.min(idx, 10) * 35}ms` }}
              >
                <FactCard fact={fact} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
