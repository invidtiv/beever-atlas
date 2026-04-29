/**
 * Vitest unit tests for `mintLoaderUrl` (issue #89).
 *
 * Covers:
 *   - first call hits POST /api/auth/loader-token and caches the token
 *   - second call within 30s of expiry hits the cache (no second POST)
 *   - `forceRefresh: true` bypasses the cache
 *   - mint endpoint 4xx → falls back to `buildLoaderUrl` (raw key)
 *   - mint endpoint 5xx → falls back to `buildLoaderUrl`
 *   - network error → falls back
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  _resetLoaderTokenCache,
  buildLoaderUrl,
  mintLoaderUrl,
} from "../api";

const _MINT_URL_RE = /\/api\/auth\/loader-token$/;

function makeMockResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

beforeEach(() => {
  _resetLoaderTokenCache();
  vi.stubGlobal("fetch", vi.fn());
  // Silence console.warn from fallback path so test output is readable.
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("mintLoaderUrl", () => {
  it("calls POST /api/auth/loader-token on first call and returns URL with ?loader_token=", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    const futureExp = Math.floor(Date.now() / 1000) + 300;
    fetchMock.mockResolvedValueOnce(
      makeMockResponse({ token: "tok-aaaa.sig", expires_at: futureExp }),
    );

    const url = await mintLoaderUrl("/api/files/proxy?url=https%3A%2F%2Fexample%2Ea.png");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, init] = fetchMock.mock.calls[0];
    expect(String(calledUrl)).toMatch(_MINT_URL_RE);
    expect(init?.method).toBe("POST");
    // Body sent should include the route path only (no query string).
    expect(JSON.parse(String(init?.body))).toEqual({ path: "/api/files/proxy" });
    // Returned URL has loader_token appended.
    expect(url).toContain("loader_token=tok-aaaa.sig");
    expect(url).toContain("/api/files/proxy?url=");
  });

  it("uses the cache on the second call within the freshness window", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    const futureExp = Math.floor(Date.now() / 1000) + 300;
    fetchMock.mockResolvedValueOnce(
      makeMockResponse({ token: "tok-bbbb.sig", expires_at: futureExp }),
    );

    await mintLoaderUrl("/api/files/proxy?url=A");
    const second = await mintLoaderUrl("/api/files/proxy?url=B");

    expect(fetchMock).toHaveBeenCalledTimes(1); // No second POST.
    expect(second).toContain("loader_token=tok-bbbb.sig");
    expect(second).toContain("url=B");
  });

  it("forceRefresh: true bypasses the cache and re-mints", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    const futureExp = Math.floor(Date.now() / 1000) + 300;
    fetchMock
      .mockResolvedValueOnce(makeMockResponse({ token: "tok-1.sig", expires_at: futureExp }))
      .mockResolvedValueOnce(makeMockResponse({ token: "tok-2.sig", expires_at: futureExp }));

    const first = await mintLoaderUrl("/api/files/proxy?url=A");
    const refreshed = await mintLoaderUrl("/api/files/proxy?url=A", { forceRefresh: true });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(first).toContain("loader_token=tok-1.sig");
    expect(refreshed).toContain("loader_token=tok-2.sig");
  });

  it("falls back to buildLoaderUrl on 404 from mint endpoint", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock.mockResolvedValueOnce(makeMockResponse({ detail: "not found" }, 404));

    const result = await mintLoaderUrl("/api/files/proxy?url=A");
    const expected = buildLoaderUrl("/api/files/proxy?url=A");

    expect(result).toBe(expected);
  });

  it("falls back to buildLoaderUrl on 5xx from mint endpoint", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock.mockResolvedValueOnce(makeMockResponse({ detail: "server error" }, 503));

    const result = await mintLoaderUrl("/api/files/proxy?url=A");
    expect(result).toBe(buildLoaderUrl("/api/files/proxy?url=A"));
  });

  it("falls back to buildLoaderUrl on network error", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock.mockRejectedValueOnce(new Error("network error"));

    const result = await mintLoaderUrl("/api/files/proxy?url=A");
    expect(result).toBe(buildLoaderUrl("/api/files/proxy?url=A"));
  });

  it("falls back when the response body is malformed", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock.mockResolvedValueOnce(makeMockResponse({ unexpected: true }));

    const result = await mintLoaderUrl("/api/files/proxy?url=A");
    expect(result).toBe(buildLoaderUrl("/api/files/proxy?url=A"));
  });

  it("evicts stale cache entries (close to expiry) and re-mints", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    // Token expiring in 10s — within 30s buffer, so cache hit logic
    // should treat it as stale and re-mint on second call.
    const nearExp = Math.floor(Date.now() / 1000) + 10;
    fetchMock
      .mockResolvedValueOnce(makeMockResponse({ token: "tok-stale.sig", expires_at: nearExp }))
      .mockResolvedValueOnce(
        makeMockResponse({
          token: "tok-fresh.sig",
          expires_at: Math.floor(Date.now() / 1000) + 300,
        }),
      );

    await mintLoaderUrl("/api/files/proxy?url=A");
    const second = await mintLoaderUrl("/api/files/proxy?url=A");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(second).toContain("loader_token=tok-fresh.sig");
  });
});
