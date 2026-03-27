import { useEffect, useState } from "react";
import type { HealthResponse } from "@/lib/types";
import { api } from "@/lib/api";

interface HealthBadgeProps {
  collapsed?: boolean;
}

type BadgeStatus = "healthy" | "degraded" | "unhealthy" | "loading";

const statusConfig: Record<
  BadgeStatus,
  { color: string; bg: string; label: string }
> = {
  healthy: { color: "bg-emerald-500", bg: "bg-emerald-50", label: "All systems operational" },
  degraded: { color: "bg-amber-500", bg: "bg-amber-50", label: "Degraded" },
  unhealthy: { color: "bg-red-500", bg: "bg-red-50", label: "Systems down" },
  loading: { color: "bg-slate-400", bg: "bg-slate-50", label: "Connecting..." },
};

export function HealthBadge({ collapsed = false }: HealthBadgeProps) {
  const [status, setStatus] = useState<BadgeStatus>("loading");
  const [degradedComponents, setDegradedComponents] = useState<string[]>([]);

  useEffect(() => {
    let mounted = true;

    async function checkHealth() {
      try {
        const data = await api.get<HealthResponse>("/api/health");
        if (!mounted) return;
        setStatus(data.status);
        const down = Object.entries(data.components)
          .filter(([, c]) => c.status === "down")
          .map(([name]) => name);
        setDegradedComponents(down);
      } catch {
        if (mounted) {
          setStatus("loading");
          setDegradedComponents([]);
        }
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 30_000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const config = statusConfig[status];

  if (collapsed) {
    return (
      <div className="flex justify-center" title={config.label}>
        <span className={`w-2.5 h-2.5 rounded-full ${config.color}`} />
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2 px-2 py-1.5 rounded-md ${config.bg}`}>
      <span className={`w-2 h-2 rounded-full ${config.color}`} />
      <span className="text-xs text-slate-600 truncate">
        {degradedComponents.length > 0
          ? `${degradedComponents.join(", ")} down`
          : config.label}
      </span>
    </div>
  );
}
