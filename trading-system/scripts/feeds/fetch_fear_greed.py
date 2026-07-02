#!/usr/bin/env python3
"""Pull the Crypto Fear & Greed Index into data/milkroad.json (CONTEXT feed).

Uses alternative.me's public API -- free, no key, no login, no cookie. This is
the same number Milk Road's Crypto Pulse page displays. Verified against the
documented API shape; not live-tested from the authoring sandbox (its network
policy blocks this host too -- same restriction hit earlier with CBOE). If it
errors on your machine, paste the error and it's a quick fix.

Usage:
    python scripts/feeds/fetch_fear_greed.py
"""

import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/feeds -> trading-system
sys.path.insert(0, str(ROOT))

import requests

from trading_system.milkroad import load_milkroad, merge_milkroad, write_milkroad

URL = "https://api.alternative.me/fng/?limit=1"

LABELS = {
    (0, 25): "Extreme Fear",
    (25, 45): "Fear",
    (45, 55): "Neutral",
    (55, 75): "Greed",
    (75, 101): "Extreme Greed",
}


def label_for(value: int) -> str:
    for (lo, hi), label in LABELS.items():
        if lo <= value < hi:
            return label
    return ""


def main() -> int:
    try:
        resp = requests.get(URL, timeout=20)
    except requests.RequestException as exc:
        print(f"error: request failed ({exc})", file=sys.stderr)
        return 2
    if resp.status_code != 200:
        print(f"error: HTTP {resp.status_code}", file=sys.stderr)
        return 2
    try:
        body = resp.json()
        entry = body["data"][0]
        value = int(entry["value"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"error: unexpected response shape ({exc}); raw: {resp.text[:300]}",
              file=sys.stderr)
        return 2

    # The API's own classification, falling back to our banding if absent.
    api_label = entry.get("value_classification") or label_for(value)
    indicators = {
        "fear_greed": {"value": value, "label": api_label, "as_of": date.today().isoformat()}
    }
    data = merge_milkroad(load_milkroad(), {
        "indicators": indicators, "source": "alternative.me",
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })
    path = write_milkroad(data)
    print(f"fear_greed: {value} ({api_label}) -> {path}")
    print("run: python scripts/cockpit.py --config h1b   (to show it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
