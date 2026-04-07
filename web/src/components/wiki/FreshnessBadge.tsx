import { RefreshCw } from "lucide-react";

interface FreshnessBadgeProps {
  isStale: boolean;
  generatedAt: string;
  onRefresh: () => void;
  isRefreshing: boolean;
}

function getTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  return `${diffDays}d ago`;
}

export function FreshnessBadge({ isStale, generatedAt, onRefresh, isRefreshing }: FreshnessBadgeProps) {
  const timeAgo = getTimeAgo(generatedAt);

  return (
    <div className="mt-2 flex items-center gap-2">
      {isStale ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-500">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
          Stale
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-500">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          {timeAgo}
        </span>
      )}
      <button
        onClick={onRefresh}
        disabled={isRefreshing}
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-50 transition-colors"
        title={isRefreshing ? "Regenerating wiki..." : "Regenerate wiki"}
      >
        <RefreshCw className={`h-3 w-3 ${isRefreshing ? "animate-spin" : ""}`} />
      </button>
    </div>
  );
}
