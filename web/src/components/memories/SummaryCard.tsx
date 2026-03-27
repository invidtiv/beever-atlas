import type { MemoryTier0 } from "@/lib/types";

interface SummaryCardProps {
  summary: MemoryTier0;
}

export function SummaryCard({ summary }: SummaryCardProps) {
  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-indigo-900">
          {summary.channel_name} — Overview
        </h3>
        <span className="text-xs text-indigo-600">
          {summary.message_count.toLocaleString()} messages
        </span>
      </div>
      <p className="text-sm text-indigo-800 leading-relaxed">
        {summary.summary}
      </p>
      <p className="mt-2 text-xs text-indigo-500">
        Updated {new Date(summary.updated_at).toLocaleDateString()}
      </p>
    </div>
  );
}
