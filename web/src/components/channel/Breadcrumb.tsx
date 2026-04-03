import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

interface ChannelBreadcrumbProps {
  workspace: string;
  platform: string;
  channelName: string;
  channelId: string;
  activeTab: string;
  connectionId: string | null;
}

export function ChannelBreadcrumb({
  workspace,
  platform,
  channelName,
  channelId,
  activeTab,
  connectionId,
}: ChannelBreadcrumbProps) {
  const workspaceLink = connectionId
    ? `/channels?workspace=${connectionId}`
    : "/channels";

  return (
    <nav className="flex items-center gap-1 text-sm min-w-0" aria-label="Breadcrumb">
      <Link
        to={workspaceLink}
        className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-[120px] sm:max-w-[180px]"
        title={`${workspace} (${platform})`}
      >
        {workspace}
        {platform && <span className="text-muted-foreground/50 capitalize"> ({platform})</span>}
      </Link>

      <ChevronRight size={14} className="text-muted-foreground/40 shrink-0" />

      <Link
        to={`/channels/${channelId}/wiki`}
        className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-[100px] sm:max-w-[160px] font-medium"
        title={`#${channelName}`}
      >
        <span className="text-primary">#</span> {channelName}
      </Link>

      <ChevronRight size={14} className="text-muted-foreground/40 shrink-0" />

      <span className="text-foreground font-medium capitalize shrink-0">{activeTab}</span>
    </nav>
  );
}
