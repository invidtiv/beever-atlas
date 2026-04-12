import { useState, useCallback, useEffect } from "react";
import { useParams } from "react-router-dom";
import { PanelLeftOpen } from "lucide-react";
import { useAsk } from "@/hooks/useAsk";
import { useConversationHistory } from "@/hooks/useConversationHistory";
import { useFeedback } from "@/hooks/useFeedback";
import { useFileUpload } from "@/hooks/useFileUpload";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInputBar } from "./ChatInputBar";
import { ConversationSidebar } from "./ConversationSidebar";
import type { AnswerMode, Message } from "@/types/askTypes";

export function AskTab() {
  const { id: channelId = "" } = useParams<{ id: string }>();

  const {
    ask,
    abort,
    reset,
    retry,
    loadSession,
    messages,
    isStreaming,
    error,
    sessionId,
  } = useAsk(channelId);

  const history = useConversationHistory(channelId);
  const feedback = useFeedback(channelId);
  const fileUpload = useFileUpload(channelId);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mode, setMode] = useState<AnswerMode>("deep");

  // Refresh conversation history after streaming completes
  useEffect(() => {
    if (!isStreaming) {
      history.fetchSessions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming]);

  // Handle sending a message
  const handleSubmit = useCallback(
    (question: string, options?: { mode?: AnswerMode }) => {
      ask(question, {
        mode: options?.mode ?? mode,
        attachments: fileUpload.files,
      });
      fileUpload.clearFiles();
    },
    [ask, mode, fileUpload],
  );

  // Handle follow-up click (from empty state or follow-up pills)
  const handleFollowUp = useCallback(
    (question: string) => {
      handleSubmit(question);
    },
    [handleSubmit],
  );

  // Handle new conversation
  const handleNewConversation = useCallback(() => {
    reset();
  }, [reset]);

  // Handle session resumption
  const handleSelectSession = useCallback(
    async (sid: string) => {
      const sessionMessages = await history.loadSession(sid);
      if (sessionMessages.length > 0) {
        const converted: Message[] = sessionMessages.map((m, i) => ({
          id: `loaded-${i}`,
          role: m.role,
          content: m.content,
          citations: m.citations ?? [],
          toolCalls: [],
          thinking: [],
          metadata: null,
          isStreaming: false,
        }));
        loadSession(converted, sid);
      }
    },
    [history, loadSession],
  );

  // Handle feedback
  const handleFeedback = useCallback(
    (messageId: string, rating: "up" | "down", comment?: string) => {
      if (sessionId) {
        feedback.submitFeedback(sessionId, messageId, rating, comment);
      }
    },
    [sessionId, feedback],
  );

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;

      // Cmd+Shift+O — new conversation
      if (mod && e.shiftKey && e.key === "o") {
        e.preventDefault();
        handleNewConversation();
      }
      // Cmd+K — toggle search/sidebar
      if (mod && e.key === "k") {
        e.preventDefault();
        setSidebarOpen((prev) => !prev);
      }
      // Escape — close sidebar
      if (e.key === "Escape") {
        setSidebarOpen(false);
      }
      // Cmd+Shift+C — copy last response
      if (mod && e.shiftKey && e.key === "c") {
        const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
        if (lastAssistant?.content) {
          e.preventDefault();
          navigator.clipboard.writeText(lastAssistant.content);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [messages, handleNewConversation]);

  return (
    <div className="flex h-[calc(100vh-120px)] bg-background">
      {/* Conversation sidebar */}
      <ConversationSidebar
        sessions={history.sessions}
        activeSessionId={sessionId ?? undefined}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewConversation={handleNewConversation}
        onSelectSession={handleSelectSession}
        onRename={history.renameSession}
        onPin={history.pinSession}
        onDelete={history.deleteSession}
        searchQuery={history.searchQuery}
        onSearchChange={history.setSearchQuery}
      />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center gap-2 px-4 py-2">
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
              title="Show conversations (⌘K)"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          )}

          {error && (
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs text-red-400">{error}</span>
              <button
                onClick={retry}
                className="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
              >
                Retry
              </button>
            </div>
          )}
        </div>

        {/* Messages */}
        <ChatMessageList
          messages={messages}
          isLoading={isStreaming && messages.length > 0 && messages[messages.length - 1]?.role === "user"}
          onFollowUpClick={handleFollowUp}
          onFeedback={handleFeedback}
          feedbackMap={feedback.feedbackMap}
          sessionId={sessionId ?? undefined}
        />

        {/* Input */}
        <ChatInputBar
          onSubmit={handleSubmit}
          onAbort={abort}
          isStreaming={isStreaming}
          mode={mode}
          onModeChange={setMode}
          attachments={fileUpload.files}
          onFileUpload={(file) => fileUpload.uploadFile(file)}
          onRemoveAttachment={fileUpload.removeFile}
          uploading={fileUpload.uploading}
        />
      </div>
    </div>
  );
}

export default AskTab;
