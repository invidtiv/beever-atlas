import { cn } from "@/lib/utils";
import type { SyncConfig } from "@/lib/types";

interface SchedulePickerProps {
  triggerMode: string;
  intervalMinutes: number | null;
  cronExpression: string | null;
  onChange: (sync: Partial<SyncConfig>) => void;
}

const MODES = [
  { value: "manual", label: "Manual", hint: "You decide when to sync" },
  { value: "interval", label: "Interval", hint: "Sync on a regular schedule" },
  { value: "cron", label: "Custom schedule", hint: "Use a cron expression" },
] as const;

const QUICK_INTERVALS = [
  { minutes: 5, label: "5 min" },
  { minutes: 15, label: "15 min" },
  { minutes: 30, label: "30 min" },
  { minutes: 60, label: "1 hour" },
  { minutes: 360, label: "6 hours" },
  { minutes: 1440, label: "Daily" },
] as const;

export function SchedulePicker({ triggerMode, intervalMinutes, cronExpression, onChange }: SchedulePickerProps) {
  return (
    <div className="space-y-3">
      <span className="text-sm font-medium text-foreground">Update frequency</span>

      {/* Segmented control */}
      <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5 gap-0.5">
        {MODES.map((mode) => (
          <button
            key={mode.value}
            type="button"
            onClick={() => onChange({ trigger_mode: mode.value, interval_minutes: null, cron_expression: null })}
            className={cn(
              "px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-150",
              triggerMode === mode.value
                ? "bg-card text-foreground shadow-sm border border-border"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Mode hint */}
      {triggerMode === "manual" && (
        <p className="text-sm text-muted-foreground">
          Click the Sync button on the channel page to update knowledge.
        </p>
      )}

      {triggerMode === "interval" && (
        <div className="space-y-2">
          <p className="text-[12px] text-muted-foreground">
            How often should new messages be processed?
          </p>
          <div className="flex flex-wrap gap-2">
            {QUICK_INTERVALS.map((opt) => (
              <button
                key={opt.minutes}
                type="button"
                onClick={() => onChange({ interval_minutes: opt.minutes })}
                className={cn(
                  "px-3 py-1.5 rounded-full text-sm font-medium border transition-all duration-150",
                  intervalMinutes === opt.minutes
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
                )}
              >
                {opt.label}
              </button>
            ))}
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={1}
                placeholder="Other"
                value={
                  intervalMinutes !== null && !QUICK_INTERVALS.some((q) => q.minutes === intervalMinutes)
                    ? intervalMinutes
                    : ""
                }
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val) && val > 0) onChange({ interval_minutes: val });
                }}
                className="h-9 w-20 rounded-lg border border-border bg-card px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <span className="text-sm text-muted-foreground">min</span>
            </div>
          </div>
        </div>
      )}

      {triggerMode === "cron" && (
        <div className="space-y-1.5">
          <p className="text-[12px] text-muted-foreground">
            Enter a cron expression for precise scheduling.
          </p>
          <input
            type="text"
            value={cronExpression ?? ""}
            onChange={(e) => onChange({ cron_expression: e.target.value || null })}
            placeholder="0 2 * * *"
            className="h-9 w-full max-w-xs rounded-lg border border-border bg-card px-3 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <p className="text-[11px] text-muted-foreground">
            Examples: <code className="font-mono">0 9 * * 1-5</code> weekdays at 9 AM, <code className="font-mono">0 */6 * * *</code> every 6 hours
          </p>
        </div>
      )}
    </div>
  );
}
