#!/usr/bin/env python3
"""Pull the Crypto Fear & Greed Index into data/milkroad.json (CONTEXT feed).

Two sources:
  --source coinstats    CoinStats Open API (needs COINSTATS_API_KEY -- the
                        same key already used by scripts/research/fetch_privacy.py.
                        Genuine key-based access, no scraping.) DEFAULT.
  --source alternative  alternative.me's public API -- free, no key, no login.

Both return the same underlying index (0-100, Extreme Fear..Extreme Greed) --
this is the same number Milk Road's Crypto Pulse page displays. Verified
against each provider's documented response shape via mocked tests; not
live-tested from the authoring sandbox (its network policy blocks both hosts
-- the same restriction hit earlier with CBOE). If it errors on your machine,
paste the error and it's a quick fix.

Usage:
    set COINSTATS_API_KEY=your_key
    python scripts/feeds/fetch_fear_greed.py                    # CoinStats (default)
    python scripts/feeds/fetch_fear_greed.py --source alternative  # free fallback
"""

import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/feeds -> trading-system
sys.path.insert(0, str(ROOT))

import requests

from trading_system.milkroad import load_milkroad, merge_milkroad, write_milkroad

COINSTATS_URL = "https://openapiv1.coinstats.app/insights/fear-and-greed"
ALTERNATIVE_URL = "https://api.alternative.me/fng/?limit=1"

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


class FetchError(RuntimeError):
    """Raised for any fetch/parse failure; main() catches and reports it."""


def fetch_coinstats() -> tuple[int, str]:
    key = os.environ.get("COINSTATS_API_KEY", "")
    if not key:
        raise FetchError("set COINSTATS_API_KEY (or use --source alternative)")
    resp = requests.get(
        COINSTATS_URL,
        headers={"X-API-KEY": key, "accept": "application/json"},
        timeout=20,
    )
    if resp.status_code != 200:
        raise FetchError(f"CoinStats HTTP {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    now = body.get("now", body)  # tolerate a flatter shape if the API changes
    value = int(now["value"])
    label = now.get("value_classification") or label_for(value)
    return value, label


def fetch_alternative() -> tuple[int, str]:
    resp = requests.get(ALTERNATIVE_URL, timeout=20)
    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code}")
    body = resp.json()
    entry = body["data"][0]
    value = int(entry["value"])
    label = entry.get("value_classification") or label_for(value)
    return value, label


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["coinstats", "alternative"], default="coinstats")
    args = parser.parse_args()

    try:
        if args.source == "coinstats":
            value, label = fetch_coinstats()
        else:
            value, label = fetch_alternative()
    except (FetchError, requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    indicators = {
        "fear_greed": {"value": value, "label": label, "as_of": date.today().isoformat()}
    }
    data = merge_milkroad(load_milkroad(), {
        "indicators": indicators, "source": args.source,
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })
    path = write_milkroad(data)
    print(f"fear_greed: {value} ({label}) via {args.source} -> {path}")
    print("run: python scripts/cockpit.py --config h1b   (to show it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
