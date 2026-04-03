import { useState } from "react";
import { NavLink } from "react-router-dom";
import { Hash, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { FavoriteButton } from "./FavoriteButton";

const PLATFORM_DOTS: Record<string, string> = {
  slack: "bg-purple-400",
  teams: "bg-blue-400",
  discord: "bg-indigo-400",
  telegram: "bg-cyan-400",
};

interface Channel {
  channel_id: string;
  name: string;
  platform: string;
  is_member: boolean;
  member_count: number | null;
  connection_id: string | null;
}

interface WorkspaceGroupProps {
  label: string;
  platform: string;
  channels: Channel[];
  defaultCollapsed: boolean;
  onToggleCollapse: () => void;
  isFavorite: (channelId: string) => boolean;
  onToggleFavorite: (channel: { channel_id: string; connection_id: string | null }) => void;
  showWorkspaceName?: boolean;
}

export function WorkspaceGroup({
  label,
  platform,
  channels,
  defaultCollapsed,
  onToggleCollapse,
  isFavorite,
  onToggleFavorite,
  showWorkspaceName,
}: WorkspaceGroupProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const handleToggle = () => {
    setCollapsed(!collapsed);
    onToggleCollapse();
  };

  // Sort: member first, then alphabetically
  const sorted = [...channels].sort((a, b) => {
    if (a.is_member !== b.is_member) return a.is_member ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="px-2 pb-1">
      <button
        onClick={handleToggle}
        className="flex items-center gap-1.5 w-full px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors rounded-md hover:bg-muted/50"
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", PLATFORM_DOTS[platform] ?? "bg-muted-foreground/40")} />
        <span className="truncate">{label}</span>
        {platform && <span className="capitalize text-muted-foreground/40 font-normal normal-case">{platform}</span>}
        <span className="ml-auto text-muted-foreground/40 tabular-nums">{channels.length}</span>
      </button>

      {!collapsed &&
        sorted.map((ch) => (
          <NavLink
            key={ch.channel_id}
            to={`/channels/${ch.channel_id}`}
            state={{
              channel_name: ch.name,
              platform: ch.platform,
              is_member: ch.is_member,
              member_count: ch.member_count,
              connection_id: ch.connection_id,
            }}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm transition-colors group ml-1",
                isActive
                  ? "bg-primary/10 text-primary dark:bg-primary/15 dark:text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
              )
            }
          >
            <span className={cn(
              "w-2 h-2 rounded-full shrink-0",
              ch.is_member ? "bg-emerald-500" : "bg-muted-foreground/30"
            )} />
            <Hash size={14} className="shrink-0 opacity-50" />
            <span className={cn("truncate flex-1", !ch.is_member && "opacity-60")}>
              {ch.name}
            </span>
            {showWorkspaceName && (
              <span className="text-[10px] text-muted-foreground/50 truncate max-w-[60px] shrink-0">
                {label}
              </span>
            )}
            <FavoriteButton
              isFavorite={isFavorite(ch.channel_id)}
              onToggle={() => onToggleFavorite({ channel_id: ch.channel_id, connection_id: ch.connection_id })}
            />
          </NavLink>
        ))}
    </div>
  );
}
