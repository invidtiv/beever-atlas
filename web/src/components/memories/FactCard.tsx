import { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import type { MemoryTier2 } from "@/lib/types";

interface FactCardProps {
  fact: MemoryTier2;
}

function qualityBadgeColor(score: number): string {
  if (score >= 7) return "bg-emerald-100 text-emerald-700";
  if (score >= 4) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

function importanceBadge(importance: string): string {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    high: "bg-orange-100 text-orange-700",
    medium: "bg-blue-100 text-blue-700",
    low: "bg-slate-100 text-slate-600",
  };
  return colors[importance] || colors.low;
}

export function FactCard({ fact }: FactCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md border border-slate-100 bg-slate-50 hover:bg-white transition-colors">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-2 p-3 text-left"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-slate-400 mt-0.5 shrink-0" />
        ) : (
          <ChevronRight size={14} className="text-slate-400 mt-0.5 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-800 leading-relaxed">
            {fact.memory}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span
              className={`px-1.5 py-0.5 text-xs font-medium rounded ${qualityBadgeColor(fact.quality_score)}`}
            >
              {fact.quality_score.toFixed(1)}
            </span>
            <span
              className={`px-1.5 py-0.5 text-xs rounded ${importanceBadge(fact.importance)}`}
            >
              {fact.importance}
            </span>
            <span className="text-xs text-slate-400">
              {fact.user_name} &middot;{" "}
              {new Date(fact.timestamp).toLocaleDateString()}
            </span>
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-3 py-2 space-y-1.5">
          <div className="flex flex-wrap gap-1">
            {fact.entity_tags.map((tag) => (
              <span
                key={tag}
                className="px-1.5 py-0.5 text-xs rounded bg-indigo-50 text-indigo-600"
              >
                {tag}
              </span>
            ))}
            {fact.topic_tags.map((tag) => (
              <span
                key={tag}
                className="px-1.5 py-0.5 text-xs rounded bg-slate-100 text-slate-500"
              >
                {tag}
              </span>
            ))}
          </div>
          <a
            href={fact.permalink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800"
          >
            <ExternalLink size={12} />
            View original message
          </a>
        </div>
      )}
    </div>
  );
}
