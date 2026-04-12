import React, { useRef, useState, useEffect, useCallback } from "react";
import { Send, Square, Paperclip, X } from "lucide-react";
import type { AnswerMode, AttachmentFile } from "../../types/askTypes";

interface ChatInputBarProps {
  onSubmit: (question: string, options?: { mode?: AnswerMode; attachments?: AttachmentFile[] }) => void;
  onAbort?: () => void;
  isStreaming: boolean;
  disabled?: boolean;
  mode: AnswerMode;
  onModeChange: (mode: AnswerMode) => void;
  attachments?: AttachmentFile[];
  onFileUpload?: (file: File) => void;
  onRemoveAttachment?: (fileId: string) => void;
  uploading?: boolean;
}

const MODE_OPTIONS: { value: AnswerMode; label: string; description: string }[] = [
  { value: "quick", label: "Quick", description: "Fast 1-3 sentence answer from cached wiki" },
  { value: "deep", label: "Deep Research", description: "Thorough answer using all knowledge sources" },
  { value: "summarize", label: "Summarize", description: "Structured bullet-point summary" },
];

export function ChatInputBar({
  onSubmit,
  onAbort,
  isStreaming,
  disabled,
  mode,
  onModeChange,
  attachments = [],
  onFileUpload,
  onRemoveAttachment,
  uploading,
}: ChatInputBarProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showModeMenu, setShowModeMenu] = useState(false);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 150) + "px"; // max ~6 lines
  }, []);

  useEffect(() => adjustHeight(), [text, adjustHeight]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSubmit(trimmed, { mode, attachments });
    setText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    files.forEach(f => onFileUpload?.(f));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const currentMode = MODE_OPTIONS.find(m => m.value === mode) ?? MODE_OPTIONS[1];

  return (
    <div className="bg-background px-4 py-3">
      <div className="max-w-3xl mx-auto w-full">
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {attachments.map((att) => (
              <span
                key={att.file_id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-card rounded-md text-xs text-foreground/90 border border-border"
              >
                📎 {att.filename}
                <button onClick={() => onRemoveAttachment?.(att.file_id)} className="text-muted-foreground/60 hover:text-foreground/90">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div
          className="flex items-end gap-2 bg-card rounded-xl border border-border focus-within:border-primary/40 transition-colors p-2"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {/* Attachment button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming || uploading}
            className="p-1.5 text-muted-foreground/60 hover:text-foreground/90 disabled:opacity-50 transition-colors shrink-0"
            title="Attach file"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.png,.jpg,.jpeg,.docx,.txt,.csv"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onFileUpload?.(file);
              e.target.value = "";
            }}
          />

          {/* Mode selector */}
          <div className="relative shrink-0">
            <button
              onClick={() => setShowModeMenu(!showModeMenu)}
              className="px-2 py-1 text-[11px] rounded-md bg-background text-muted-foreground hover:text-foreground/90 border border-border transition-colors"
            >
              {currentMode.label}
            </button>
            {showModeMenu && (
              <div className="absolute bottom-full left-0 mb-1 bg-card border border-border rounded-lg shadow-xl py-1 w-56 z-50">
                {MODE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => { onModeChange(opt.value); setShowModeMenu(false); }}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors ${
                      mode === opt.value ? "text-blue-400" : "text-foreground/90"
                    }`}
                  >
                    <div className="font-medium">{opt.label}</div>
                    <div className="text-[11px] text-muted-foreground/60">{opt.description}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? "Waiting for response..." : "Message this channel knowledge base..."}
            disabled={isStreaming || disabled}
            rows={1}
            className="flex-1 bg-transparent text-foreground text-sm resize-none outline-none placeholder-muted-foreground/50 disabled:opacity-50 py-1"
          />

          {/* Send/Stop button */}
          {isStreaming ? (
            <button
              onClick={onAbort}
              className="p-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors shrink-0"
              title="Stop generating"
            >
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!text.trim() || disabled}
              className="p-2 bg-primary hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground text-white rounded-lg transition-colors shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
