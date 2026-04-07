import type { WikiPageNode } from "@/lib/types";

interface TopicCardProps {
  topic: WikiPageNode;
  onClick: () => void;
}

export function TopicCard({ topic, onClick }: TopicCardProps) {
  return (
    <button
      onClick={onClick}
      className="text-left w-full rounded-xl border border-border bg-card p-4 hover:border-primary/40 hover:shadow-sm transition-all duration-150"
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-xs text-muted-foreground/70 font-mono">{topic.section_number}</span>
        {topic.memory_count > 0 && (
          <span className="text-xs text-muted-foreground shrink-0">{topic.memory_count} memories</span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-foreground leading-snug">{topic.title}</h3>
    </button>
  );
}
