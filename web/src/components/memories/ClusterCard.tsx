import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { MemoryTier1, MemoryTier2 } from "@/lib/types";
import { FactCard } from "./FactCard";

interface ClusterCardProps {
  cluster: MemoryTier1;
  facts: MemoryTier2[];
}

export function ClusterCard({ cluster, facts }: ClusterCardProps) {
  const [expanded, setExpanded] = useState(false);

  const memberFacts = facts.filter((f) => f.cluster_id === cluster.id);

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-slate-50 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={16} className="text-slate-400 shrink-0" />
        ) : (
          <ChevronRight size={16} className="text-slate-400 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-medium text-slate-900 truncate">
              {cluster.topic}
            </h4>
            <span className="text-xs text-slate-400 shrink-0">
              {cluster.fact_count} facts
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 truncate">
            {cluster.summary}
          </p>
        </div>
        <div className="flex gap-1 shrink-0">
          {cluster.topic_tags.map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 text-xs rounded bg-slate-100 text-slate-600"
            >
              {tag}
            </span>
          ))}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 p-3 space-y-2">
          {memberFacts.length > 0 ? (
            memberFacts.map((fact) => <FactCard key={fact.id} fact={fact} />)
          ) : (
            <p className="text-xs text-slate-400 p-2">
              No facts in this cluster.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
