import { describe, it } from "node:test";
import assert from "node:assert";
import type { IncomingMessage, ServerResponse } from "node:http";
import { WebhookBuffer } from "./webhook-buffer.js";
import type { ChatManager } from "./chat-manager.js";

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Minimal ChatManager stub — only isTransitioning() is needed by WebhookBuffer. */
function makeMockChatManager(transitioning: boolean): ChatManager {
  return {
    isTransitioning: () => transitioning,
  } as unknown as ChatManager;
}

interface MockRes {
  statusCode: number | undefined;
  headers: Record<string, string>;
  body: string;
  headersSent: boolean;
  writeHead(code: number, headers?: Record<string, string>): void;
  end(data?: string): void;
}

function makeMockRes(): MockRes {
  const res: MockRes = {
    statusCode: undefined,
    headers: {},
    body: "",
    headersSent: false,
    writeHead(code, headers = {}) {
      this.statusCode = code;
      this.headers = { ...this.headers, ...headers };
      this.headersSent = true;
    },
    end(data = "") {
      this.body = data;
    },
  };
  return res;
}

function makeMockReq(): IncomingMessage {
  return {} as IncomingMessage;
}

// ── shouldBuffer() ────────────────────────────────────────────────────────────

describe("WebhookBuffer — shouldBuffer()", () => {
  it("returns false when chatManager is not transitioning", () => {
    const buf = new WebhookBuffer(makeMockChatManager(false));
    assert.strictEqual(buf.shouldBuffer(), false);
  });

  it("returns true when chatManager is transitioning", () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    assert.strictEqual(buf.shouldBuffer(), true);
  });
});

// ── enqueue() ────────────────────────────────────────────────────────────────

describe("WebhookBuffer — enqueue()", () => {
  it("increases queueSize by one after a single enqueue", () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    const req = makeMockReq();
    const res = makeMockRes();

    // Do not await — the promise only resolves when drained or timed out
    buf.enqueue(req, res as unknown as ServerResponse);

    assert.strictEqual(buf.queueSize(), 1);
  });

  it("accumulates multiple enqueued requests in order", () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));

    buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);
    buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);
    buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);

    assert.strictEqual(buf.queueSize(), 3);
  });
});

// ── drain() ───────────────────────────────────────────────────────────────────

describe("WebhookBuffer — drain()", () => {
  it("calls the handler once for each queued request", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    const req1 = makeMockReq();
    const req2 = makeMockReq();
    const res1 = makeMockRes();
    const res2 = makeMockRes();

    const p1 = buf.enqueue(req1, res1 as unknown as ServerResponse);
    const p2 = buf.enqueue(req2, res2 as unknown as ServerResponse);

    const handledReqs: IncomingMessage[] = [];
    const handler = async (req: IncomingMessage, _res: ServerResponse) => {
      handledReqs.push(req);
    };

    buf.drain(handler);
    await Promise.all([p1, p2]);

    assert.strictEqual(handledReqs.length, 2);
    assert.strictEqual(handledReqs[0], req1);
    assert.strictEqual(handledReqs[1], req2);
  });

  it("empties the queue after drain", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    const p = buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);

    buf.drain(async () => {});
    await p;

    assert.strictEqual(buf.queueSize(), 0);
  });

  it("resolves the enqueue promise after the handler completes", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    const res = makeMockRes();
    let resolved = false;

    const p = buf.enqueue(makeMockReq(), res as unknown as ServerResponse).then(() => {
      resolved = true;
    });

    assert.strictEqual(resolved, false);
    buf.drain(async () => {});
    await p;
    assert.strictEqual(resolved, true);
  });

  it("responds 500 and still resolves when the handler throws", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    const res = makeMockRes();

    const p = buf.enqueue(makeMockReq(), res as unknown as ServerResponse);

    buf.drain(async () => {
      throw new Error("handler failure");
    });

    await p; // must not throw / hang

    // drain catches the error and writes 500 when headers not yet sent
    assert.strictEqual(res.statusCode, 500);
  });
});

// ── Buffer overflow (maxSize = 100) ───────────────────────────────────────────

describe("WebhookBuffer — buffer overflow", () => {
  it("responds 503 BUFFER_FULL immediately when queue is at maxSize", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));

    // Fill the queue to maxSize (default 100) without draining
    for (let i = 0; i < 100; i++) {
      buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);
    }

    assert.strictEqual(buf.queueSize(), 100);

    const overflowRes = makeMockRes();
    await buf.enqueue(makeMockReq(), overflowRes as unknown as ServerResponse);

    assert.strictEqual(overflowRes.statusCode, 503);
    const parsed = JSON.parse(overflowRes.body);
    assert.strictEqual(parsed.code, "BUFFER_FULL");
  });

  it("does not add overflow request to the queue", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));

    for (let i = 0; i < 100; i++) {
      buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);
    }

    await buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);

    // Queue must remain at exactly 100, not 101
    assert.strictEqual(buf.queueSize(), 100);
  });
});

// ── maxDuration timeout ───────────────────────────────────────────────────────

describe("WebhookBuffer — maxDuration timeout", () => {
  it("responds 503 TRANSITION_TIMEOUT and resolves when timeout fires", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    // Override maxDurationMs to something very short for the test
    (buf as any).maxDurationMs = 20;

    const res = makeMockRes();
    await buf.enqueue(makeMockReq(), res as unknown as ServerResponse);

    assert.strictEqual(res.statusCode, 503);
    const parsed = JSON.parse(res.body);
    assert.strictEqual(parsed.code, "TRANSITION_TIMEOUT");
  });

  it("removes the timed-out entry from the queue", async () => {
    const buf = new WebhookBuffer(makeMockChatManager(true));
    (buf as any).maxDurationMs = 20;

    await buf.enqueue(makeMockReq(), makeMockRes() as unknown as ServerResponse);

    assert.strictEqual(buf.queueSize(), 0);
  });
});
