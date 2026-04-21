"""Check message counts for all channels a Mattermost bot can see.

Usage:
    MATTERMOST_BASE_URL=https://mattermost.example.com \\
    MATTERMOST_BOT_TOKEN=<your-bot-token> \\
    python scripts/check_mattermost_channels.py
"""

from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    base_url = os.environ.get("MATTERMOST_BASE_URL", "").rstrip("/")
    token = os.environ.get("MATTERMOST_BOT_TOKEN", "")
    if not base_url or not token:
        print("Set MATTERMOST_BASE_URL and MATTERMOST_BOT_TOKEN", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=f"{base_url}/api/v4", headers=headers, timeout=15) as client:
        me = client.get("/users/me").raise_for_status().json()
        bot_id = me["id"]
        print(f"Bot: @{me['username']} ({bot_id})\n")

        teams = client.get("/users/me/teams").raise_for_status().json()
        print(f"{'Team':<20} {'Channel':<35} {'Root':>6} {'Total':>6}")
        print("-" * 70)

        for team in teams:
            channels = (
                client.get(f"/users/{bot_id}/teams/{team['id']}/channels")
                .raise_for_status()
                .json()
            )
            for ch in sorted(channels, key=lambda c: c.get("name", "")):
                if ch.get("type") in ("D", "G") or ch.get("delete_at", 0) > 0:
                    continue
                print(
                    f"{team['display_name']:<20} "
                    f"{ch.get('display_name') or ch.get('name'):<35} "
                    f"{ch.get('total_msg_count_root', 0):>6} "
                    f"{ch.get('total_msg_count', 0):>6}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
