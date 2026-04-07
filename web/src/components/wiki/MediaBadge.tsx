interface MediaBadgeProps {
  type: "pdf" | "image" | "link" | "video" | "audio";
  name?: string;
}

const icons: Record<string, string> = {
  pdf: "📄",
  image: "🖼️",
  link: "🔗",
  video: "🎬",
  audio: "🎙️",
};

export function MediaBadge({ type, name }: MediaBadgeProps) {
  return (
    <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
      <span>{icons[type] || "📎"}</span>
      {name && <span className="truncate max-w-[120px]">{name}</span>}
    </span>
  );
}
