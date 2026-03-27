import { useParams } from "react-router-dom";
import { useMemories } from "@/hooks/useMemories";
import { SummaryCard } from "./SummaryCard";
import { ClusterCard } from "./ClusterCard";
import { MemoryFilters } from "./MemoryFilters";

export function TierBrowser() {
  const { id } = useParams<{ id: string }>();
  const { summary, clusters, facts, filters, setFilters, isLoading } =
    useMemories(id ?? "");

  if (isLoading) {
    return (
      <div className="p-6 text-center text-slate-500">Loading memories...</div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <SummaryCard summary={summary} />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">
            Topic Clusters
          </h3>
          <span className="text-xs text-slate-400">
            {clusters.length} clusters &middot; {facts.length} facts
          </span>
        </div>

        <MemoryFilters filters={filters} setFilters={setFilters} />

        {clusters.map((cluster) => (
          <ClusterCard key={cluster.id} cluster={cluster} facts={facts} />
        ))}
      </div>
    </div>
  );
}
