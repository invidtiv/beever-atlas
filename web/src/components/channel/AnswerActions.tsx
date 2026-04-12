import React, { useState } from "react";
import { Copy, ThumbsUp, ThumbsDown, Check } from "lucide-react";
import type { Message } from "../../types/askTypes";

interface AnswerActionsProps {
  message: Message;
  onFeedback?: (messageId: string, rating: "up" | "down", comment?: string) => void;
  feedback?: { rating: "up" | "down"; comment?: string };
}

export function AnswerActions({ message, onFeedback, feedback }: AnswerActionsProps) {
  const [copied, setCopied] = useState(false);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = (rating: "up" | "down") => {
    if (rating === "down" && !showComment) {
      setShowComment(true);
      onFeedback?.(message.id, rating);
    } else {
      onFeedback?.(message.id, rating);
      setShowComment(false);
    }
  };

  const submitComment = () => {
    if (comment.trim()) {
      onFeedback?.(message.id, "down", comment.trim());
      setShowComment(false);
      setComment("");
    }
  };

  return (
    <div className="mt-2">
      <div className="flex items-center gap-1">
        <button
          onClick={handleCopy}
          className="p-1.5 text-muted-foreground/60 hover:text-foreground/90 rounded transition-colors"
          title={copied ? "Copied!" : "Copy response"}
        >
          {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
        <button
          onClick={() => handleFeedback("up")}
          className={`p-1.5 rounded transition-colors ${
            feedback?.rating === "up" ? "text-green-400 bg-green-400/10" : "text-muted-foreground/60 hover:text-foreground/90"
          }`}
          title="Good answer"
        >
          <ThumbsUp className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => handleFeedback("down")}
          className={`p-1.5 rounded transition-colors ${
            feedback?.rating === "down" ? "text-red-400 bg-red-400/10" : "text-muted-foreground/60 hover:text-foreground/90"
          }`}
          title="Bad answer"
        >
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>
      </div>

      {showComment && feedback?.rating === "down" && (
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitComment()}
            placeholder="What went wrong?"
            className="flex-1 text-xs bg-muted border border-border rounded-md px-3 py-1.5 text-foreground/90 placeholder-muted-foreground/50 outline-none focus:border-primary/40"
          />
          <button
            onClick={submitComment}
            className="text-xs px-3 py-1.5 bg-blue-600/20 text-blue-400 rounded-md hover:bg-blue-600/30 transition-colors"
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}
