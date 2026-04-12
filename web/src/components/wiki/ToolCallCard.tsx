import { Loader2, Check } from "lucide-react";
import { getToolLabel } from "../../constants/toolLabels";
import type { ToolCallEvent } from "../../types/askTypes";

interface ToolCallCardProps {
  toolCall: ToolCallEvent;
}

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const label = getToolLabel(toolCall.tool_name);
  const isRunning = toolCall.status === "running";

  return (
    <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
      <span className="mt-0.5 shrink-0">
        {isRunning ? (
          <Loader2 size={13} className="animate-spin text-primary" />
        ) : (
          <Check size={13} className="text-emerald-500" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground">{label}</span>
          {toolCall.latency_ms !== undefined && (
            <span className="text-xs text-muted-foreground">
              {toolCall.latency_ms}ms
            </span>
          )}
          {toolCall.facts_found !== undefined && toolCall.facts_found > 0 && (
            <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
              {toolCall.facts_found} results
            </span>
          )}
        </div>
        {toolCall.result_summary && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {toolCall.result_summary}
          </p>
        )}
      </div>
    </div>
  );
}
