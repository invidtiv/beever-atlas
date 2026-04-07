import { Clock, Calendar, Hand } from "lucide-react";
import { useChannelPolicy } from "@/hooks/useChannelPolicy";

interface NextSyncBadgeProps {
  channelId: string;
}

export function NextSyncBadge({ channelId }: NextSyncBadgeProps) {
  const { policy, isLoading } = useChannelPolicy(channelId);

  if (isLoading || !policy) return null;

  const mode = policy.effective.sync.trigger_mode;
  const intervalMinutes = policy.effective.sync.interval_minutes;

  if (mode === "interval" && intervalMinutes != null) {
    const label = intervalMinutes < 60 ? `Every ${intervalMinutes}m` : `Every ${intervalMinutes / 60}h`;
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-muted text-muted-foreground">
        <Clock className="h-3 w-3 shrink-0" />
        {label}
      </span>
    );
  }

  if (mode === "cron") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-muted text-muted-foreground">
        <Calendar className="h-3 w-3 shrink-0" />
        Scheduled
      </span>
    );
  }

  if (mode === "manual") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-muted text-muted-foreground">
        <Hand className="h-3 w-3 shrink-0" />
        Manual
      </span>
    );
  }

  return null;
}
