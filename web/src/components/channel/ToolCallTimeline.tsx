import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import type { ToolCallEvent } from "../../types/askTypes";
import { getToolLabel, TOOL_CATEGORIES, CATEGORY_COLORS } from "../../constants/toolLabels";

interface ToolCallTimelineProps {
  toolCalls: ToolCallEvent[];
  isStreaming: boolean;
}

function ToolCallCard({ tc }: { tc: ToolCallEvent }) {
  const [expanded, setExpanded] = useState(false);
  const category = TOOL_CATEGORIES[tc.tool_name] ?? "search";
  const colorClass = CATEGORY_COLORS[category] ?? "text-muted-foreground";
  const label = getToolLabel(tc.tool_name);

  const latencyColor =
    tc.status === "error" ? "text-red-400" :
    (tc.latency_ms ?? 0) > 5000 ? "text-red-400" :
    (tc.latency_ms ?? 0) > 2000 ? "text-amber-400" :
    "text-green-400";

  return (
    <div className="relative pl-6 py-1.5 px-2 rounded-lg">
      {/* Timeline dot */}
      <div className={`absolute left-2 top-3 w-3 h-3 rounded-full border-2 ${
        tc.status === "running"
          ? "border-amber-400 bg-transparent animate-pulse"
          : tc.status === "error"
            ? "border-red-400 bg-red-400/30"
            : "border-green-400 bg-green-400/30"
      }`} />

      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs w-full text-left hover:bg-muted/50 rounded px-1.5 py-1 -ml-1.5 transition-colors"
      >
        <span className={`font-medium ${colorClass}`}>{label}</span>

        {tc.status === "running" ? (
          <span className="text-amber-400 animate-pulse">running...</span>
        ) : (
          <>
            <span className={`${latencyColor}`}>{tc.latency_ms}ms</span>
            {tc.facts_found != null && tc.facts_found > 0 && (
              <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded text-[10px]">
                {tc.facts_found} found
              </span>
            )}
          </>
        )}

        {tc.status !== "running" && (
          expanded
            ? <ChevronDown className="w-3 h-3 text-muted-foreground/40 ml-auto" />
            : <ChevronRight className="w-3 h-3 text-muted-foreground/40 ml-auto" />
        )}
      </button>

      {expanded && tc.status !== "running" && (
        <div className="mt-1 ml-1.5 text-[11px] text-muted-foreground/60 space-y-1 pb-1">
          {tc.input && Object.keys(tc.input).length > 0 && (
            <div>
              <span className="text-muted-foreground/40">Input: </span>
              <span className="font-mono">{JSON.stringify(tc.input, null, 0).slice(0, 200)}</span>
            </div>
          )}
          {tc.result_summary && (
            <div>
              <span className="text-muted-foreground/40">Result: </span>
              <span>{tc.result_summary}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolCallTimeline({ toolCalls, isStreaming }: ToolCallTimelineProps) {
  const [collapsed, setCollapsed] = useState(false);

  // Auto-collapse when streaming ends
  useEffect(() => {
    if (!isStreaming && toolCalls.length > 0 && toolCalls.every(tc => tc.status !== "running")) {
      setCollapsed(true);
    }
  }, [isStreaming, toolCalls]);

  if (toolCalls.length === 0) return null;

  return (
    <div className="mb-3">
      {collapsed ? (
        <button
          onClick={() => setCollapsed(false)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-muted/50 rounded-lg text-xs text-muted-foreground hover:text-foreground/90 transition-colors"
        >
          <ChevronRight className="w-3.5 h-3.5" />
          <Wrench className="w-3.5 h-3.5 text-amber-400" />
          <span>Used {toolCalls.length} tool{toolCalls.length !== 1 ? "s" : ""}</span>
        </button>
      ) : (
        <div>
          <button
            onClick={() => setCollapsed(true)}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground/90 transition-colors mb-2"
          >
            <ChevronDown className="w-3.5 h-3.5" />
            <Wrench className="w-3.5 h-3.5 text-amber-400" />
            <span>Tools ({toolCalls.length})</span>
          </button>
          <div className="border-l border-border ml-1.5 space-y-1">
            {toolCalls.map((tc, i) => (
              <ToolCallCard key={`${tc.tool_name}-${i}`} tc={tc} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
