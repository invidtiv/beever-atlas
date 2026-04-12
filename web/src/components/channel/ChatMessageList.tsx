import { useRef, useEffect, useState } from "react";
import type { Message } from "@/types/askTypes";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";
import { MessageSkeleton } from "./MessageSkeleton";
import { ChevronDown } from "lucide-react";

interface ChatMessageListProps {
  messages: Message[];
  isLoading: boolean;
  onCitationClick?: (citation: any) => void;
  onFollowUpClick?: (question: string) => void;
  onFeedback?: (messageId: string, rating: "up" | "down", comment?: string) => void;
  feedbackMap?: Record<string, { rating: "up" | "down"; comment?: string }>;
  sessionId?: string;
}

export function ChatMessageList({
  messages,
  isLoading,
  onCitationClick,
  onFollowUpClick,
  onFeedback,
  feedbackMap = {},
  sessionId,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [userScrolled, setUserScrolled] = useState(false);

  // Auto-scroll to bottom when new messages arrive (unless user scrolled up)
  useEffect(() => {
    if (!userScrolled) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, userScrolled]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollBtn(!atBottom);
    setUserScrolled(!atBottom);
  };

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    setUserScrolled(false);
  };

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
            <span className="text-2xl">?</span>
          </div>
          <h3 className="text-lg font-medium text-foreground mb-2">Ask anything about this channel</h3>
          <p className="text-sm text-muted-foreground mb-6">
            I can search through wiki pages, facts, relationships, and more to answer your questions.
          </p>
          <div className="grid grid-cols-1 gap-2 text-left">
            {[
              "What is this channel about?",
              "Who are the key contributors?",
              "What decisions were made recently?",
              "What topics are discussed most?",
            ].map((q) => (
              <button
                key={q}
                onClick={() => onFollowUpClick?.(q)}
                className="px-4 py-2.5 text-sm text-foreground/90 bg-card rounded-xl hover:bg-muted transition-colors text-left border border-border"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 relative overflow-hidden">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-4 md:px-8 py-6 space-y-6"
      >
        <div className="max-w-3xl mx-auto w-full space-y-6">
          {messages.map((msg) =>
            msg.role === "user" ? (
              <UserMessage key={msg.id} message={msg} />
            ) : (
              <AssistantMessage
                key={msg.id}
                message={msg}
                onCitationClick={onCitationClick}
                onFollowUpClick={onFollowUpClick}
                onFeedback={onFeedback}
                feedback={feedbackMap[msg.id]}
                sessionId={sessionId}
              />
            )
          )}
          {isLoading && messages[messages.length - 1]?.role === "user" && <MessageSkeleton />}
          <div ref={bottomRef} />
        </div>
      </div>

      {showScrollBtn && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-muted hover:bg-muted/80 text-foreground/90 rounded-full p-2 shadow-lg transition-all border border-border"
        >
          <ChevronDown className="w-5 h-5" />
        </button>
      )}
    </div>
  );
}
