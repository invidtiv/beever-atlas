import { Zap, Calendar, Feather, Hand } from "lucide-react";
import { cn } from "@/lib/utils";
import { POLICY_PRESETS } from "@/lib/policy-presets";

interface PresetSelectorProps {
  selectedPreset: string | null;
  onSelect: (presetId: string) => void;
}

const PRESET_META: Record<string, {
  icon: React.ComponentType<{ className?: string }>;
  bullets: string[];
}> = {
  "real-time": {
    icon: Zap,
    bullets: ["Every 5 minutes", "Full depth", "Auto-organize"],
  },
  "daily-digest": {
    icon: Calendar,
    bullets: ["Daily at 2 AM", "Full depth", "Auto-organize"],
  },
  "lightweight": {
    icon: Feather,
    bullets: ["Every hour", "Quick scan", "Manual organize"],
  },
  "manual": {
    icon: Hand,
    bullets: ["On demand", "Full depth", "Manual organize"],
  },
};

export function PresetSelector({ selectedPreset, onSelect }: PresetSelectorProps) {
  const isCustom = selectedPreset === "custom";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-foreground">
          How should this channel stay up to date?
        </span>
        {isCustom && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            Customized
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {POLICY_PRESETS.map((preset) => {
          const meta = PRESET_META[preset.id];
          const Icon = meta?.icon ?? Zap;
          const bullets = meta?.bullets ?? [];
          const isSelected = selectedPreset === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => onSelect(preset.id)}
              className={cn(
                "group relative flex flex-col items-start gap-2.5 rounded-2xl border p-4 text-left transition-all duration-150",
                "hover:shadow-sm hover:shadow-black/5 dark:hover:shadow-black/20",
                isSelected
                  ? "border-primary bg-primary/5 shadow-sm"
                  : "border-border bg-card hover:border-primary/40 hover:bg-muted/30",
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                  isSelected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground group-hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 space-y-1.5">
                <div
                  className={cn(
                    "text-sm font-medium leading-tight",
                    isSelected ? "text-primary" : "text-foreground",
                  )}
                >
                  {preset.name}
                </div>
                <ul className="space-y-0.5">
                  {bullets.map((b) => (
                    <li key={b} className="text-[11px] leading-snug text-muted-foreground flex items-center gap-1">
                      <span className={cn(
                        "inline-block w-1 h-1 rounded-full shrink-0",
                        isSelected ? "bg-primary/60" : "bg-muted-foreground/40",
                      )} />
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
