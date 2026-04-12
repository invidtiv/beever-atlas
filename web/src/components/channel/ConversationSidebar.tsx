import { useState } from "react";
import { Plus, Search, X, Clock, Pin, PanelLeftClose } from "lucide-react";
import type { ConversationSession } from "../../hooks/useConversationHistory";
import { ConversationItem } from "./ConversationItem";

interface ConversationSidebarProps {
  sessions: ConversationSession[];
  activeSessionId?: string;
  isOpen: boolean;
  onClose: () => void;
  onNewConversation: () => void;
  onSelectSession: (sessionId: string) => void;
  onRename: (sessionId: string, title: string) => void;
  onPin: (sessionId: string, pinned: boolean) => void;
  onDelete: (sessionId: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function ConversationSidebar({
  sessions,
  activeSessionId,
  isOpen,
  onClose,
  onNewConversation,
  onSelectSession,
  onRename,
  onPin,
  onDelete,
  searchQuery,
  onSearchChange,
}: ConversationSidebarProps) {
  const pinnedSessions = sessions.filter((s) => s.pinned);
  const unpinnedSessions = sessions.filter((s) => !s.pinned);
  const [searchFocused, setSearchFocused] = useState(false);

  return (
    <div
      className={`shrink-0 h-full border-r border-border/50 bg-muted/30 flex flex-col overflow-hidden transition-all duration-200 ease-in-out ${
        isOpen ? "w-64" : "w-0 border-r-0"
      }`}
    >
      <div className={`w-64 h-full flex flex-col ${isOpen ? "opacity-100" : "opacity-0"}`}>
        {/* Header */}
        <div className="px-3 pt-3 pb-2 flex items-center justify-between">
          <button
            onClick={onNewConversation}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-foreground bg-background hover:bg-muted border border-border rounded-lg transition-colors"
            title="New conversation (⌘⇧O)"
          >
            <Plus className="w-3.5 h-3.5" />
            New chat
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
            title="Close sidebar (⌘K)"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div
            className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 transition-all ${
              searchFocused
                ? "bg-background ring-1 ring-primary/30"
                : "bg-background/60"
            }`}
          >
            <Search className="w-3.5 h-3.5 text-muted-foreground/50 shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              placeholder="Search conversations..."
              className="bg-transparent text-xs text-foreground placeholder-muted-foreground/40 outline-none w-full"
            />
            {searchQuery && (
              <button
                onClick={() => onSearchChange("")}
                className="text-muted-foreground/50 hover:text-muted-foreground"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto px-2 pb-3">
          {sessions.length === 0 ? (
            <p className="text-xs text-muted-foreground/50 text-center py-8">
              Your conversations will appear here
            </p>
          ) : (
            <div className="space-y-0.5">
              {pinnedSessions.length > 0 && (
                <div className="mb-2">
                  <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] text-muted-foreground/50 uppercase tracking-widest font-medium">
                    <Pin className="w-2.5 h-2.5" />
                    Pinned
                  </div>
                  <div className="space-y-0.5">
                    {pinnedSessions.map((s) => (
                      <ConversationItem
                        key={s.session_id}
                        session={s}
                        isActive={s.session_id === activeSessionId}
                        onSelect={() => onSelectSession(s.session_id)}
                        onRename={(title) => onRename(s.session_id, title)}
                        onPin={() => onPin(s.session_id, !s.pinned)}
                        onDelete={() => onDelete(s.session_id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {unpinnedSessions.length > 0 && (
                <div>
                  {pinnedSessions.length > 0 && (
                    <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] text-muted-foreground/50 uppercase tracking-widest font-medium">
                      <Clock className="w-2.5 h-2.5" />
                      Recent
                    </div>
                  )}
                  <div className="space-y-0.5">
                    {unpinnedSessions.map((s) => (
                      <ConversationItem
                        key={s.session_id}
                        session={s}
                        isActive={s.session_id === activeSessionId}
                        onSelect={() => onSelectSession(s.session_id)}
                        onRename={(title) => onRename(s.session_id, title)}
                        onPin={() => onPin(s.session_id, !s.pinned)}
                        onDelete={() => onDelete(s.session_id)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="px-3 py-1.5 border-t border-border/30">
          <p className="text-[10px] text-muted-foreground/40 text-center">
            ⌘K toggle · ⌘⇧O new chat
          </p>
        </div>
      </div>
    </div>
  );
}
