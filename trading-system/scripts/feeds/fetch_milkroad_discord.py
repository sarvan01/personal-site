#!/usr/bin/env python3
"""TEMPLATE — pull Milk Road trade posts from a Discord channel into
data/milkroad.json (CONTEXT feed, NOT a trading signal).

Uses YOUR OWN Discord bot. You are responsible for Terms-of-Service compliance:
reading paid signals via automation is your judgment call, and you must NEVER
use a personal user token / self-bot (that violates Discord's ToS and can get
your account banned). Use a proper bot you created and invited to the server,
with the Message Content intent enabled in the Developer Portal.

Setup:
    pip install discord.py
    set DISCORD_BOT_TOKEN=...        (your bot token)
    python scripts/feeds/fetch_milkroad_discord.py --channel <CHANNEL_ID> --limit 40

You must adapt parse_trade() to Milk Road's actual message format — the regex
below is only a placeholder guess.
"""

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/feeds -> trading-system
sys.path.insert(0, str(ROOT))

from trading_system.milkroad import load_milkroad, merge_milkroad, write_milkroad


def parse_trade(content: str) -> dict | None:
    """Return {action, asset, note} or None. ADAPT to the real format."""
    m = re.search(r"\b(BUY|SELL|HOLD|WATCH|TRIM|ADD)\b[:\s]+\$?([A-Z]{2,6})", content, re.I)
    if not m:
        return None
    return {"action": m.group(1).upper(), "asset": m.group(2).upper(),
            "note": content.strip().replace("\n", " ")[:160]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True, type=int, help="Discord channel ID")
    parser.add_argument("--limit", type=int, default=40, help="messages to scan")
    args = parser.parse_args()

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("error: set DISCORD_BOT_TOKEN (your own bot token).", file=sys.stderr)
        return 2
    try:
        import discord
    except ImportError:
        print("error: pip install discord.py", file=sys.stderr)
        return 2

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    collected: list[dict] = []

    @client.event
    async def on_ready():
        try:
            ch = client.get_channel(args.channel) or await client.fetch_channel(args.channel)
            async for msg in ch.history(limit=args.limit):
                t = parse_trade(msg.content or "")
                if t:
                    t["date"] = msg.created_at.strftime("%Y-%m-%d")
                    t["source"] = "discord"
                    collected.append(t)
        finally:
            await client.close()

    client.run(token)

    if not collected:
        print("no trades parsed — adapt parse_trade() to the channel's format.",
              file=sys.stderr)
        return 1
    data = merge_milkroad(load_milkroad(), {"trades": collected, "source": "discord"})
    path = write_milkroad(data)
    print(f"wrote {len(collected)} trades -> {path}")
    print("run: python scripts/cockpit.py --config h1b   (to show them)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
