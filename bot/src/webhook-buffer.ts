/**
 * WebhookBuffer — queues incoming webhook requests during Chat instance transitions.
 *
 * When ChatManager rebuilds the Chat instance (adapter add/remove), there is a brief
 * window where the bot is unavailable. This buffer holds incoming requests during
 * that window and replays them once the new instance is ready.
 */

import type { IncomingMessage, ServerResponse } from "node:http";
import type { ChatManager } from "./chat-manager.js";

// ── Types ────────────────────────────────────────────────────────────────────

interface QueueEntry {
  req: IncomingMessage;
  res: ServerResponse;
  resolve: () => void;
}

type RequestHandler = (req: IncomingMessage, res: ServerResponse) => Promise<void>;

// ── WebhookBuffer ─────────────────────────────────────────────────────────────

export class WebhookBuffer {
  private queue: QueueEntry[] = [];
  private maxSize: number = 100;
  private maxDurationMs: number = 5000;
  private chatManager: ChatManager;

  constructor(chatManager: ChatManager) {
    this.chatManager = chatManager;
  }

  shouldBuffer(): boolean {
    return this.chatManager.isTransitioning();
  }

  /**
   * Enqueue a request to be replayed once the transition completes.
   * If the queue is full, responds 503 immediately.
   */
  enqueue(req: IncomingMessage, res: ServerResponse): Promise<void> {
    if (this.queue.length >= this.maxSize) {
      res.writeHead(503, {
        "Content-Type": "application/json",
        "Retry-After": "1",
      });
      res.end(JSON.stringify({ error: "Service temporarily unavailable", code: "BUFFER_FULL" }));
      return Promise.resolve();
    }

    return new Promise<void>((resolve) => {
      this.queue.push({ req, res, resolve });

      // Safety timeout — drain after maxDurationMs even if still transitioning
      setTimeout(() => {
        const idx = this.queue.findIndex((e) => e.resolve === resolve);
        if (idx !== -1) {
          const [entry] = this.queue.splice(idx, 1);
          entry.res.writeHead(503, {
            "Content-Type": "application/json",
            "Retry-After": "1",
          });
          entry.res.end(JSON.stringify({ error: "Bot transition timed out", code: "TRANSITION_TIMEOUT" }));
          entry.resolve();
        }
      }, this.maxDurationMs);
    });
  }

  /**
   * Replay all queued requests through the provided handler.
   * Called after a successful Chat rebuild.
   */
  drain(handler: RequestHandler): void {
    const entries = this.queue.splice(0);
    for (const entry of entries) {
      handler(entry.req, entry.res)
        .catch((err: unknown) => {
          console.error("WebhookBuffer: error replaying buffered request:", err);
          if (!entry.res.headersSent) {
            entry.res.writeHead(500);
            entry.res.end("Internal Server Error");
          }
        })
        .finally(() => {
          entry.resolve();
        });
    }
  }

  queueSize(): number {
    return this.queue.length;
  }
}
