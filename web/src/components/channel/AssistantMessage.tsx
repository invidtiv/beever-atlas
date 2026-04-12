import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "@/types/askTypes";
import { ThinkingSection } from "./ThinkingSection";
import { ToolCallTimeline } from "./ToolCallTimeline";
import { AnswerActions } from "./AnswerActions";
import { FollowUpSuggestions } from "./FollowUpSuggestions";

interface AssistantMessageProps {
  message: Message;
  onCitationClick?: (citation: any) => void;
  onFollowUpClick?: (question: string) => void;
  onFeedback?: (messageId: string, rating: "up" | "down", comment?: string) => void;
  feedback?: { rating: "up" | "down"; comment?: string };
  sessionId?: string;
}

const MODE_BADGES: Record<string, { label: string; color: string }> = {
  quick: { label: "Quick", color: "bg-green-500/20 text-green-400 border-green-500/30" },
  deep: { label: "Deep Research", color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  summarize: { label: "Summarize", color: "bg-purple-500/20 text-purple-400 border-purple-500/30" },
};

export function AssistantMessage({
  message,
  onCitationClick,
  onFollowUpClick,
  onFeedback,
  feedback,
  sessionId,
}: AssistantMessageProps) {
  const modeBadge = message.mode ? MODE_BADGES[message.mode] : null;

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
        B
      </div>
      <div className="flex-1 min-w-0 max-w-none">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-foreground/90">Beever Atlas</span>
          {modeBadge && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${modeBadge.color}`}>
              {modeBadge.label}
            </span>
          )}
        </div>

        {/* Thinking section */}
        {message.thinking && message.thinking.length > 0 && (
          <ThinkingSection
            thinking={message.thinking}
            isStreaming={message.isStreaming}
            durationMs={message.thinkingDuration ?? null}
          />
        )}

        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <ToolCallTimeline
            toolCalls={message.toolCalls}
            isStreaming={message.isStreaming}
          />
        )}

        {/* Response content */}
        {message.content && (
          <div className="prose prose-invert prose-sm max-w-none text-foreground/90">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p className="mb-3 leading-relaxed">{children}</p>,
                ul: ({ children }) => <ul className="mb-3 space-y-1 list-disc list-inside">{children}</ul>,
                ol: ({ children }) => <ol className="mb-3 space-y-1 list-decimal list-inside">{children}</ol>,
                li: ({ children }) => <li className="text-foreground/90">{children}</li>,
                code: ({ className, children, ...props }) => {
                  const isInline = !className;
                  return isInline ? (
                    <code className="px-1.5 py-0.5 bg-muted rounded text-primary text-xs" {...props}>{children}</code>
                  ) : (
                    <code className={`block p-3 bg-muted rounded-lg text-xs overflow-x-auto ${className ?? ""}`} {...props}>{children}</code>
                  );
                },
                table: ({ children }) => (
                  <div className="overflow-x-auto mb-3">
                    <table className="text-sm border-collapse border border-border">{children}</table>
                  </div>
                ),
                th: ({ children }) => <th className="px-3 py-2 bg-muted border border-border text-left text-foreground/90">{children}</th>,
                td: ({ children }) => <td className="px-3 py-2 border border-border text-muted-foreground">{children}</td>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-amber-500/50 pl-4 text-muted-foreground italic mb-3">{children}</blockquote>
                ),
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">{children}</a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Streaming indicator */}
        {message.isStreaming && !message.content && message.thinking?.length === 0 && (
          <div className="flex items-center gap-1.5 text-muted-foreground text-sm">
            <span className="flex gap-1">
              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
          </div>
        )}

        {/* Actions (only when not streaming) */}
        {!message.isStreaming && message.content && (
          <AnswerActions
            message={message}
            onFeedback={onFeedback}
            feedback={feedback}
          />
        )}

        {/* Follow-up suggestions */}
        {!message.isStreaming && message.followUps && message.followUps.length > 0 && (
          <FollowUpSuggestions
            suggestions={message.followUps}
            onSelect={onFollowUpClick}
          />
        )}
      </div>
    </div>
  );
}
