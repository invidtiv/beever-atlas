import { NavLink } from "react-router-dom";
import { Hash, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { FavoriteButton } from "./FavoriteButton";

interface Channel {
  channel_id: string;
  name: string;
  platform: string;
  is_member: boolean;
  member_count: number | null;
  connection_id: string | null;
}

interface FavoritesListProps {
  channels: Channel[];
  getWorkspaceName: (connectionId: string | null) => string;
  onToggleFavorite: (channel: { channel_id: string; connection_id: string | null }) => void;
}

export function FavoritesList({ channels, getWorkspaceName, onToggleFavorite }: FavoritesListProps) {
  if (channels.length === 0) return null;

  return (
    <div className="px-2 pb-1">
      <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-amber-500/80 flex items-center gap-1">
        <Star size={10} fill="currentColor" />
        Favorites
      </p>
      {channels.map((ch) => (
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
              "flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm transition-colors group",
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
          <span className="truncate flex-1">{ch.name}</span>
          <span className="text-[10px] text-muted-foreground/50 truncate max-w-[60px] shrink-0">
            {getWorkspaceName(ch.connection_id)}
          </span>
          <FavoriteButton
            isFavorite={true}
            onToggle={() => onToggleFavorite({ channel_id: ch.channel_id, connection_id: ch.connection_id })}
          />
        </NavLink>
      ))}
    </div>
  );
}
