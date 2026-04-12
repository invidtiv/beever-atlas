import type { Message } from "@/types/askTypes";

interface UserMessageProps {
  message: Message;
}

function getInitials(name?: string): string {
  if (!name) return "U";
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function formatTime(date?: Date | string): string {
  if (!date) return "";
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 60000) return "Just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString();
}

export function UserMessage({ message }: UserMessageProps) {
  return (
    <div className="flex justify-end gap-3">
      <div className="max-w-[70%]">
        <div className="bg-primary/10 rounded-2xl px-4 py-3">
          <p className="text-foreground text-sm whitespace-pre-wrap">{message.content}</p>
          {message.attachments && message.attachments.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {message.attachments.map((att) => (
                <span
                  key={att.file_id}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-blue-500/10 rounded-md text-xs text-blue-300 border border-blue-500/20"
                >
                  📎 {att.filename}
                  <span className="text-blue-400/60">
                    ({(att.size_bytes / 1024).toFixed(0)}KB)
                  </span>
                </span>
              ))}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground/60 mt-1 text-right">{formatTime(new Date())}</p>
      </div>
      <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-xs font-medium text-white shrink-0">
        {getInitials()}
      </div>
    </div>
  );
}
