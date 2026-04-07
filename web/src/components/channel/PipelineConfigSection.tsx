import { useState } from "react";
import { ChevronDown, ChevronRight, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { IngestionConfig, ConsolidationConfig, ConsolidationStrategy } from "@/lib/types";

interface PipelineConfigSectionProps {
  ingestion: IngestionConfig;
  consolidation: ConsolidationConfig;
  onIngestionChange: (config: Partial<IngestionConfig>) => void;
  onConsolidationChange: (config: Partial<ConsolidationConfig>) => void;
  /** Show max_concurrent_syncs control (only for global defaults) */
  showConcurrency?: boolean;
  maxConcurrentSyncs?: number;
  onConcurrencyChange?: (value: number) => void;
}

const ORGANIZE_OPTIONS: { value: ConsolidationStrategy; label: string; hint: string }[] = [
  { value: "after_every_sync", label: "Automatically", hint: "Organize into topics after each sync" },
  { value: "after_n_syncs", label: "After several syncs", hint: "Wait to batch up changes before organizing" },
  { value: "manual", label: "Manually", hint: "You trigger organization when ready" },
];

function Toggle({ checked, onChange, label, hint }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-sm text-foreground">{label}</div>
        <div className="text-[11px] text-muted-foreground mt-0.5">{hint}</div>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1",
          checked ? "bg-primary" : "bg-muted-foreground/30",
        )}
      >
        <span
          className={cn(
            "pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
            checked ? "translate-x-4" : "translate-x-0",
          )}
        />
      </button>
    </div>
  );
}

export function PipelineConfigSection({
  ingestion,
  consolidation,
  onIngestionChange,
  onConsolidationChange,
  showConcurrency,
  maxConcurrentSyncs,
  onConcurrencyChange,
}: PipelineConfigSectionProps) {
  const [open, setOpen] = useState(false);

  const qualityThreshold = ingestion.quality_threshold ?? 0.5;
  const strategy = consolidation.strategy ?? "after_every_sync";
  const deepAnalysis = !(ingestion.skip_entity_extraction ?? false);

  // Summary of current advanced settings for collapsed state
  const summaryParts: string[] = [];
  if (deepAnalysis) summaryParts.push("Deep analysis");
  else summaryParts.push("Quick scan");
  if (strategy === "after_every_sync") summaryParts.push("auto-organize");
  else if (strategy === "manual") summaryParts.push("manual organize");
  else summaryParts.push("batched organize");

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-5 py-4 text-left hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Advanced</span>
          {!open && (
            <span className="text-[11px] text-muted-foreground ml-1">
              {summaryParts.join(" / ")}
            </span>
          )}
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="border-t border-border px-5 py-4 space-y-6">
          {/* Knowledge depth — combines entity extraction + graph writes */}
          <div className="space-y-3">
            <div>
              <div className="text-sm font-medium text-foreground">Knowledge depth</div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Controls how thoroughly messages are analyzed
              </div>
            </div>

            <Toggle
              checked={deepAnalysis}
              onChange={(v) => {
                onIngestionChange({
                  skip_entity_extraction: !v,
                  skip_graph_writes: !v,
                });
              }}
              label="Deep analysis"
              hint="Extract people, projects, decisions and build a knowledge graph. Slower but richer."
            />

            {/* Quality filter */}
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-foreground">Quality filter</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    Only keep facts above this quality score
                  </div>
                </div>
                <span className="text-sm font-mono text-muted-foreground tabular-nums">{qualityThreshold.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={qualityThreshold}
                onChange={(e) => onIngestionChange({ quality_threshold: parseFloat(e.target.value) })}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-[11px] text-muted-foreground/60">
                <span>Keep everything</span>
                <span>Only important facts</span>
              </div>
            </div>
          </div>

          {/* Organization — replaces "Consolidation strategy" */}
          <div className="space-y-3">
            <div>
              <div className="text-sm font-medium text-foreground">Topic organization</div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                When to group facts into topics and generate summaries
              </div>
            </div>

            <div className="space-y-1.5">
              {ORGANIZE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={cn(
                    "flex items-start gap-2.5 cursor-pointer rounded-lg px-3 py-2 transition-colors",
                    strategy === opt.value ? "bg-primary/5" : "hover:bg-muted/30",
                  )}
                >
                  <input
                    type="radio"
                    name="organize_strategy"
                    value={opt.value}
                    checked={strategy === opt.value}
                    onChange={() => onConsolidationChange({ strategy: opt.value })}
                    className="accent-primary mt-0.5"
                  />
                  <div>
                    <div className="text-sm text-foreground">{opt.label}</div>
                    <div className="text-[11px] text-muted-foreground">{opt.hint}</div>
                  </div>
                </label>
              ))}
            </div>

            {strategy === "after_n_syncs" && (
              <div className="flex items-center gap-2 pl-3">
                <span className="text-sm text-muted-foreground">Organize after</span>
                <input
                  type="number"
                  min={2}
                  value={consolidation.after_n_syncs ?? ""}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    onConsolidationChange({ after_n_syncs: isNaN(val) ? null : val });
                  }}
                  placeholder="3"
                  className="h-9 w-16 rounded-lg border border-border bg-card px-3 text-sm text-foreground text-center placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <span className="text-sm text-muted-foreground">syncs</span>
              </div>
            )}
          </div>

          {/* Max concurrent syncs — global defaults only */}
          {showConcurrency && onConcurrencyChange && (
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm text-foreground">Parallel syncs</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    Maximum channels syncing at the same time
                  </div>
                </div>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={maxConcurrentSyncs ?? 3}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val) && val > 0) onConcurrencyChange(val);
                  }}
                  className="h-9 w-20 rounded-lg border border-border bg-card px-3 text-sm text-foreground text-center placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
