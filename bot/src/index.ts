import { config } from "dotenv";
import { resolve } from "node:path";
import { createServer, IncomingMessage, ServerResponse } from "node:http";

// Load .env from project root (one level up from bot/)
config({ path: resolve(import.meta.dirname, "../../.env") });
import { Chat } from "chat";
import { formatBlockKit } from "./formatter.js";
import { consumeSSEStream } from "./sse-client.js";
import { registerBridgeRoutes } from "./bridge.js";
import { ChatManager } from "./chat-manager.js";
import { WebhookBuffer } from "./webhook-buffer.js";

// ── Environment validation ──────────────────────────────────────────────────

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
const PORT = parseInt(process.env.BOT_PORT || "3001", 10);

function validateEnv(): void {
  // Warn (not exit) when Slack env vars are missing — platform connections can
  // be loaded at runtime from the backend database.
  const slackMissing = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"].filter(
    (key) => !process.env[key],
  );
  if (slackMissing.length > 0) {
    console.warn(
      `Warning: Slack env vars not set (${slackMissing.join(", ")}). ` +
        "Bot will start without Slack until a connection is registered via the backend.",
    );
  }
}

// ── Handler registration ─────────────────────────────────────────────────────

function registerHandlers(bot: Chat): void {
  // Handler: user @mentions the bot
  bot.onNewMention(async (thread, message) => {
    console.log(`[@mention] ${message.text} (from ${thread.id})`);
    await thread.subscribe();

    const channelId = extractChannelId(thread.id);
    const question = stripMention(message.text || "");

    if (!question.trim()) {
      await thread.post("Please ask me a question! For example: @beever what is our tech stack?");
      return;
    }

    try {
      const result = await askBackend(channelId, question);
      const blocks = formatBlockKit(result.answer, result.citations, result.route);
      await thread.post(blocks);
    } catch (err) {
      console.error("Error processing mention:", err);
      await thread.post("Sorry, I encountered an error processing your question. Please try again.");
    }
  });

  // Handler: follow-up messages in subscribed threads
  bot.onSubscribedMessage(async (thread, message) => {
    console.log(`[subscribed] ${message.text} (in ${thread.id})`);

    const channelId = extractChannelId(thread.id);
    const question = message.text || "";

    if (!question.trim()) return;

    try {
      const result = await askBackend(channelId, question);
      const blocks = formatBlockKit(result.answer, result.citations, result.route);
      await thread.post(blocks);
    } catch (err) {
      console.error("Error processing follow-up:", err);
      await thread.post("Sorry, I encountered an error. Please try again.");
    }
  });
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function extractChannelId(threadId: string): string {
  // Chat SDK thread IDs follow pattern: "slack:CHANNEL_ID:THREAD_TS"
  const parts = threadId.split(":");
  return parts.length >= 2 ? parts[1] : threadId;
}

function stripMention(text: string): string {
  // Remove Slack @mention format: <@U12345> or <@U12345|username>
  return text.replace(/<@[A-Z0-9]+(\|[^>]+)?>/g, "").trim();
}

export interface AskResult {
  answer: string;
  citations: Array<{ type: string; text: string }>;
  route: string;
  confidence: number;
  costUsd: number;
}

async function askBackend(channelId: string, question: string): Promise<AskResult> {
  const url = `${BACKEND_URL}/api/channels/${channelId}/ask`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}: ${await response.text()}`);
  }

  return consumeSSEStream(response);
}

// ── Startup sync with retry ──────────────────────────────────────────────────

async function loadConnectionsFromBackend(chatManager: ChatManager): Promise<void> {
  const delays = [1000, 2000, 4000, 8000, 16000];
  const BRIDGE_API_KEY = process.env.BRIDGE_API_KEY || "";

  for (let attempt = 0; attempt < delays.length; attempt++) {
    try {
      const headers: Record<string, string> = {};
      if (BRIDGE_API_KEY) {
        headers["Authorization"] = `Bearer ${BRIDGE_API_KEY}`;
      }
      const response = await fetch(`${BACKEND_URL}/api/internal/connections/credentials`, { headers });
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const connections = await response.json() as Array<{
        connection_id?: string;
        platform: string;
        credentials: Record<string, string>;
        status: string;
      }>;

      if (connections.length === 0) {
        console.log("Startup sync: no connections found in backend");
        return;
      }

      for (const conn of connections) {
        console.log(`Startup sync: registering ${conn.platform} adapter (connection: ${conn.connection_id || "legacy"})`);
        await chatManager.register(conn.platform, conn.credentials, conn.connection_id);
      }

      console.log(`Startup sync: loaded ${connections.length} connection(s) from backend`);
      return;
    } catch (err) {
      const isLastAttempt = attempt === delays.length - 1;
      if (isLastAttempt) {
        console.warn(`Startup sync: all ${delays.length} attempts failed. Falling back to .env credentials.`);
        await fallbackToEnvCredentials(chatManager);
      } else {
        const waitMs = delays[attempt];
        console.warn(`Startup sync: attempt ${attempt + 1} failed (${err}), retrying in ${waitMs}ms...`);
        await new Promise((r) => setTimeout(r, waitMs));
      }
    }
  }
}

async function fallbackToEnvCredentials(chatManager: ChatManager): Promise<void> {
  const botToken = process.env.SLACK_BOT_TOKEN;
  const signingSecret = process.env.SLACK_SIGNING_SECRET;

  if (botToken && signingSecret) {
    console.log("Startup sync: registering Slack adapter from .env credentials");
    await chatManager.register("slack", { botToken, signingSecret });
  } else {
    console.warn("Startup sync: no .env credentials available — bot starting without adapters");
  }
}

// ── HTTP server for webhooks ────────────────────────────────────────────────

function startServer(chatManager: ChatManager): void {
  const handleBridge = registerBridgeRoutes(chatManager);
  const webhookBuffer = new WebhookBuffer(chatManager);

  const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    // Health check
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        status: "ok",
        adapters: chatManager.listAdapters(),
        transitioning: chatManager.isTransitioning(),
      }));
      return;
    }

    // Bridge endpoints (Chat SDK data fetching for Python backend)
    if (req.url?.startsWith("/bridge/")) {
      await handleBridge(req, res);
      return;
    }

    // Buffer webhook requests during Chat instance transitions
    if (webhookBuffer.shouldBuffer()) {
      await webhookBuffer.enqueue(req, res);
      return;
    }

    // Per-connection webhook endpoint (preferred for multi-workspace)
    const connWebhookMatch = req.method === "POST" && req.url?.match(/^\/api\/webhooks\/([^/]+)$/);
    if (connWebhookMatch) {
      await handleConnectionWebhook(req, res, chatManager, PORT, connWebhookMatch[1]);
      return;
    }

    // Legacy platform webhooks (try all adapters for that platform)
    if (req.method === "POST" && req.url === "/api/slack") {
      await handlePlatformWebhook(req, res, chatManager, PORT, "slack");
      return;
    }
    if (req.method === "POST" && req.url === "/api/discord") {
      await handlePlatformWebhook(req, res, chatManager, PORT, "discord");
      return;
    }
    if (req.method === "POST" && req.url === "/api/teams") {
      await handlePlatformWebhook(req, res, chatManager, PORT, "teams");
      return;
    }
    if (req.method === "POST" && req.url === "/api/telegram") {
      await handlePlatformWebhook(req, res, chatManager, PORT, "telegram");
      return;
    }

    res.writeHead(404);
    res.end("Not Found");
  });

  server.listen(PORT, () => {
    console.log(`Bot server listening on port ${PORT}`);
    console.log(`Connection webhook: POST http://localhost:${PORT}/api/webhooks/{connectionId}`);
    console.log(`Legacy Slack:       POST http://localhost:${PORT}/api/slack`);
    console.log(`Legacy Discord:     POST http://localhost:${PORT}/api/discord`);
    console.log(`Legacy Teams:       POST http://localhost:${PORT}/api/teams`);
    console.log(`Legacy Telegram:    POST http://localhost:${PORT}/api/telegram`);
    console.log(`Bridge API:         GET  http://localhost:${PORT}/bridge/*`);
    console.log(`Health check:       GET  http://localhost:${PORT}/health`);
  });

  // Graceful shutdown
  const shutdown = async () => {
    console.log("Shutting down bot service...");
    server.close();
    const bot = chatManager.getCurrentBot();
    if (bot) {
      await bot.shutdown().catch(() => {});
    }
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

/**
 * Per-connection webhook: routes directly to the adapter by connection ID.
 */
async function handleConnectionWebhook(
  req: IncomingMessage,
  res: ServerResponse,
  chatManager: ChatManager,
  port: number,
  connectionId: string,
): Promise<void> {
  try {
    const bot = chatManager.getCurrentBot();
    if (!bot) {
      res.writeHead(503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Bot not initialized" }));
      return;
    }

    const compositeKey = chatManager.getCompositeKeyForConnection(connectionId);
    if (!compositeKey) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: `Connection ${connectionId} not found` }));
      return;
    }

    const body = await readBody(req);
    const webReq = new Request(`http://localhost:${port}${req.url}`, {
      method: "POST",
      headers: Object.fromEntries(
        Object.entries(req.headers)
          .filter((e): e is [string, string] => typeof e[1] === "string"),
      ),
      body,
    });

    const webhooks = bot.webhooks as any;
    if (typeof webhooks[compositeKey] === "function") {
      const webRes = await webhooks[compositeKey](webReq);
      console.log(`Webhook handled by connection ${connectionId} (${compositeKey})`);
      res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
      const resBody = await webRes.text();
      res.end(resBody);
    } else {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: `No webhook handler for connection ${connectionId}` }));
    }
  } catch (err) {
    console.error(`Connection webhook error (${connectionId}):`, err);
    res.writeHead(500);
    res.end("Internal Server Error");
  }
}

/**
 * Legacy platform webhook: tries all adapters for the platform sequentially.
 * The first adapter whose handleWebhook() returns a non-error response wins.
 */
async function handlePlatformWebhook(
  req: IncomingMessage,
  res: ServerResponse,
  chatManager: ChatManager,
  port: number,
  platform: string,
): Promise<void> {
  try {
    const bot = chatManager.getCurrentBot();
    if (!bot) {
      res.writeHead(503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Bot not initialized" }));
      return;
    }

    const adapters = chatManager.getAdaptersByPlatform(platform);
    if (adapters.length === 0) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: `${platform} adapter not connected` }));
      return;
    }

    const body = await readBody(req);
    const webhooks = bot.webhooks as any;

    // Try each adapter for the platform; first successful response wins
    for (const { compositeKey, connectionId } of adapters) {
      if (typeof webhooks[compositeKey] !== "function") continue;

      try {
        const webReq = new Request(`http://localhost:${port}${req.url}`, {
          method: "POST",
          headers: Object.fromEntries(
            Object.entries(req.headers)
              .filter((e): e is [string, string] => typeof e[1] === "string"),
          ),
          body,
        });
        const webRes = await webhooks[compositeKey](webReq);

        // If verification succeeded (non-4xx), use this response
        if (webRes.status < 400) {
          console.log(`Legacy ${platform} webhook handled by connection ${connectionId}`);
          res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
          const resBody = await webRes.text();
          res.end(resBody);
          return;
        }
      } catch {
        // This adapter couldn't handle it, try next
      }
    }

    // No adapter could handle it — try the last one anyway to return its error
    const lastKey = adapters[adapters.length - 1].compositeKey;
    const webReq = new Request(`http://localhost:${port}${req.url}`, {
      method: "POST",
      headers: Object.fromEntries(
        Object.entries(req.headers)
          .filter((e): e is [string, string] => typeof e[1] === "string"),
      ),
      body,
    });
    const webRes = await webhooks[lastKey](webReq);
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    const resBody = await webRes.text();
    res.end(resBody);
  } catch (err) {
    console.error(`${platform} webhook error:`, err);
    res.writeHead(500);
    res.end("Internal Server Error");
  }
}

const MAX_BODY_SIZE = 1_048_576; // 1 MB

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    let size = 0;
    req.on("data", (chunk: Buffer) => {
      size += chunk.length;
      if (size > MAX_BODY_SIZE) {
        req.destroy();
        reject(new Error("Request body too large"));
        return;
      }
      data += chunk.toString();
    });
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  validateEnv();
  console.log("Initializing Beever Atlas bot...");
  console.log(`Backend URL: ${BACKEND_URL}`);
  console.log(`Redis URL: ${REDIS_URL}`);

  const chatManager = new ChatManager(REDIS_URL, registerHandlers);

  // Attempt to load connections from backend with retry + .env fallback
  await loadConnectionsFromBackend(chatManager);

  startServer(chatManager);
  console.log("Bot service ready");
}

main().catch((err: unknown) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
