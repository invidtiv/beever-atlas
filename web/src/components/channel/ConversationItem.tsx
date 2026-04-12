import { useState } from "react";
import { MoreHorizontal, Pin, Pencil, Trash2 } from "lucide-react";
import type { ConversationSession } from "../../hooks/useConversationHistory";

interface ConversationItemProps {
  session: ConversationSession;
  isActive: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onPin: () => void;
  onDelete: () => void;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  if (diff < 60000) return "Just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}d`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ConversationItem({
  session,
  isActive,
  onSelect,
  onRename,
  onPin,
  onDelete,
}: ConversationItemProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(
    session.title || session.first_question,
  );

  const displayTitle =
    session.title || session.first_question || "Untitled conversation";

  const handleRename = () => {
    if (editTitle.trim()) {
      onRename(editTitle.trim());
      setEditing(false);
    }
  };

  return (
    <div
      className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 ${
        isActive
          ? "bg-primary/10 text-foreground"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      }`}
      onClick={() => !editing && onSelect()}
    >
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename();
              if (e.key === "Escape") setEditing(false);
            }}
            onBlur={handleRename}
            autoFocus
            className="w-full text-sm bg-muted border border-border rounded-lg px-2 py-1 text-foreground outline-none focus:ring-1 focus:ring-primary/30"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <div className="flex items-center gap-2">
            {session.pinned && (
              <Pin className="w-2.5 h-2.5 text-primary/60 shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm truncate leading-snug">{displayTitle}</p>
              <p className="text-[11px] text-muted-foreground/40 mt-0.5">
                {formatRelativeTime(session.created_at)}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* More menu trigger */}
      <div className="relative shrink-0">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          }}
          className={`p-1 rounded-md transition-all ${
            showMenu
              ? "opacity-100 bg-muted"
              : "opacity-0 group-hover:opacity-100 hover:bg-muted"
          }`}
        >
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>

        {showMenu && (
          <>
            <div
              className="fixed inset-0 z-50"
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(false);
              }}
            />
            <div className="absolute right-0 top-7 bg-card border border-border rounded-xl shadow-xl py-1 w-36 z-50">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditing(true);
                  setShowMenu(false);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-foreground/80 hover:bg-muted transition-colors"
              >
                <Pencil className="w-3 h-3" /> Rename
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onPin();
                  setShowMenu(false);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-foreground/80 hover:bg-muted transition-colors"
              >
                <Pin className="w-3 h-3" /> {session.pinned ? "Unpin" : "Pin"}
              </button>
              <div className="my-1 border-t border-border/50" />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                  setShowMenu(false);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-destructive hover:bg-destructive/10 transition-colors"
              >
                <Trash2 className="w-3 h-3" /> Delete
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
