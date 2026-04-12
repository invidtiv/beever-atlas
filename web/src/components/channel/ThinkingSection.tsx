import React, { useState, useEffect } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";

interface ThinkingSectionProps {
  thinking: string[];
  isStreaming: boolean;
  durationMs: number | null;
}

export function ThinkingSection({ thinking, isStreaming, durationMs }: ThinkingSectionProps) {
  const [expanded, setExpanded] = useState(true);

  // Auto-collapse when streaming ends
  useEffect(() => {
    if (!isStreaming && thinking.length > 0) {
      setExpanded(false);
    }
  }, [isStreaming, thinking.length]);

  const thinkingText = thinking.join("");
  if (!thinkingText) return null;

  const durationLabel = durationMs
    ? `Thought for ${(durationMs / 1000).toFixed(1)}s`
    : isStreaming
      ? "Thinking..."
      : "Thought process";

  return (
    <div className="mb-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-2 px-3 py-1.5 bg-muted/50 rounded-lg text-xs text-muted-foreground hover:text-foreground/90 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5" />
        )}
        <Brain className="w-3.5 h-3.5 text-purple-400" />
        <span>{durationLabel}</span>
        {isStreaming && (
          <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" />
        )}
      </button>

      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          expanded ? "max-h-[500px] opacity-100 mt-2" : "max-h-0 opacity-0"
        }`}
      >
        <div className="bg-muted/30 rounded-xl p-4 border border-border/50 overflow-y-auto">
          <p className="text-sm text-muted-foreground/60 leading-relaxed whitespace-pre-wrap">
            {thinkingText}
          </p>
        </div>
      </div>
    </div>
  );
}
