#!/usr/bin/env python3
"""Dry-run test script for multi-platform bridge endpoints.

Tests the bot bridge API to verify that each platform adapter returns
correct HTTP status codes and response shapes for channels, messages,
and file proxy operations.

Usage:
    python scripts/test_platform_bridge.py [--bridge-url http://localhost:3000]

Requires the bot service to be running.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field

import httpx


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class TestSuite:
    results: list[TestResult] = field(default_factory=list)

    def record(self, name: str, passed: bool, detail: str = "") -> None:
        self.results.append(TestResult(name=name, passed=passed, detail=detail))
        status = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    def summary(self) -> None:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        color = "\033[32m" if failed == 0 else "\033[31m"
        print(f"\n{color}{passed}/{total} passed, {failed} failed\033[0m")

    @property
    def ok(self) -> bool:
        return all(r.passed for r in self.results)


async def run_tests(bridge_url: str, api_key: str | None) -> TestSuite:
    suite = TestSuite()
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(base_url=bridge_url, headers=headers, timeout=15.0) as client:

        # ── 1. Health / Adapter listing ──────────────────────────────────

        print("\n=== Adapter Management ===")

        r = await client.get("/bridge/adapters")
        suite.record(
            "GET /bridge/adapters returns 200",
            r.status_code == 200,
            f"status={r.status_code}",
        )

        adapters = r.json().get("adapters", [])
        suite.record(
            "Adapters list is an array",
            isinstance(adapters, list),
            f"type={type(adapters).__name__}, count={len(adapters)}",
        )

        # Build connection/platform maps for subsequent tests
        connections: dict[str, str] = {}  # connectionId -> platform
        for a in adapters:
            connections[a.get("connectionId", "")] = a.get("platform", "")

        if not connections:
            print("\n  ⚠ No adapters registered — only error-path tests available\n")

        # ── 2. Per-platform tests ────────────────────────────────────────

        tested_platforms = set()

        for conn_id, platform in connections.items():
            tested_platforms.add(platform)
            print(f"\n=== Platform: {platform} (connection: {conn_id[:12]}…) ===")

            # -- List channels --
            r = await client.get(f"/bridge/connections/{conn_id}/channels")
            if platform in ("teams", "telegram"):
                # These platforms should return 501 Not Supported
                suite.record(
                    f"[{platform}] List channels → 501",
                    r.status_code == 501,
                    f"status={r.status_code}",
                )
                code = r.json().get("code", "")
                suite.record(
                    f"[{platform}] List channels code = NOT_SUPPORTED",
                    code == "NOT_SUPPORTED",
                    f"code={code}",
                )
            else:
                suite.record(
                    f"[{platform}] List channels → 200",
                    r.status_code == 200,
                    f"status={r.status_code}",
                )
                channels = r.json().get("channels", [])
                suite.record(
                    f"[{platform}] Channels is array",
                    isinstance(channels, list),
                    f"count={len(channels)}",
                )

                # Test first channel if available
                if channels:
                    ch = channels[0]
                    ch_id = ch.get("channel_id", "")

                    # Verify channel shape
                    required_fields = {"channel_id", "name", "platform"}
                    has_fields = required_fields.issubset(ch.keys())
                    suite.record(
                        f"[{platform}] Channel has required fields",
                        has_fields,
                        f"fields={list(ch.keys())}",
                    )

                    # -- Get single channel --
                    r = await client.get(f"/bridge/connections/{conn_id}/channels/{ch_id}")
                    suite.record(
                        f"[{platform}] Get channel → 200",
                        r.status_code == 200,
                        f"status={r.status_code}",
                    )

                    # -- Get messages --
                    r = await client.get(
                        f"/bridge/connections/{conn_id}/channels/{ch_id}/messages",
                        params={"limit": "5", "order": "desc"},
                    )
                    suite.record(
                        f"[{platform}] Get messages → 200",
                        r.status_code == 200,
                        f"status={r.status_code}",
                    )

                    if r.status_code == 200:
                        msgs = r.json().get("messages", [])
                        suite.record(
                            f"[{platform}] Messages is array",
                            isinstance(msgs, list),
                            f"count={len(msgs)}",
                        )

                        if msgs:
                            msg = msgs[0]
                            msg_fields = {"content", "author", "platform", "channel_id", "message_id", "timestamp"}
                            has_msg_fields = msg_fields.issubset(msg.keys())
                            suite.record(
                                f"[{platform}] Message has required fields",
                                has_msg_fields,
                                f"fields={list(msg.keys())}",
                            )

                            # Check platform-specific features
                            if platform == "slack":
                                suite.record(
                                    f"[{platform}] Message has reactions field",
                                    "reactions" in msg,
                                )
                                suite.record(
                                    f"[{platform}] Message has links field",
                                    "links" in msg,
                                )

                            if platform == "discord":
                                suite.record(
                                    f"[{platform}] Message has reactions field",
                                    "reactions" in msg,
                                )
                                suite.record(
                                    f"[{platform}] Message has links field",
                                    "links" in msg,
                                )

            # -- Invalid channel → 404 (not 500) --
            r = await client.get(
                f"/bridge/connections/{conn_id}/channels/INVALID_CHANNEL_ID_999/messages",
                params={"limit": "5"},
            )
            if platform in ("teams", "telegram"):
                suite.record(
                    f"[{platform}] Invalid channel messages → 501",
                    r.status_code == 501,
                    f"status={r.status_code}",
                )
            else:
                suite.record(
                    f"[{platform}] Invalid channel → 404 (not 500)",
                    r.status_code in (404, 502),
                    f"status={r.status_code}",
                )

        # ── 3. Error path tests (no adapter needed) ─────────────────────

        print("\n=== Error Path Tests ===")

        # Invalid connection ID
        r = await client.get("/bridge/connections/nonexistent-conn-id/channels")
        suite.record(
            "Invalid connection → 404",
            r.status_code == 404,
            f"status={r.status_code}",
        )

        # File proxy with invalid URL
        r = await client.get("/bridge/files", params={"url": "https://invalid.example.com/file.png"})
        suite.record(
            "File proxy invalid URL → error (not crash)",
            r.status_code in (404, 500, 502, 503),
            f"status={r.status_code}",
        )

        # ── 4. Platform coverage report ──────────────────────────────────

        print("\n=== Platform Coverage ===")
        all_platforms = {"slack", "discord", "teams", "telegram"}
        for p in sorted(all_platforms):
            if p in tested_platforms:
                print(f"  ✓ {p}")
            else:
                print(f"  ○ {p} (not connected — skipped)")

    return suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Test multi-platform bridge endpoints")
    parser.add_argument("--bridge-url", default="http://localhost:3000", help="Bot bridge base URL")
    parser.add_argument("--api-key", default=None, help="Bridge API key (BRIDGE_API_KEY)")
    args = parser.parse_args()

    print(f"Testing bridge at {args.bridge_url}")
    suite = asyncio.run(run_tests(args.bridge_url, args.api_key))
    suite.summary()
    sys.exit(0 if suite.ok else 1)


if __name__ == "__main__":
    main()
