#!/usr/bin/env python3
"""Pull Milk Road macro-index / macro-pulse / crypto-pulse into
data/milkroad.json (CONTEXT feed, NOT a trading signal).

Milk Road has no public API, and these pages are premium content behind your
login. This script hits the underlying JSON endpoints your browser calls
(the pages themselves render client-side, so scraping raw HTML gets nothing).
You find those endpoints once via your browser's DevTools; see
docs/milkroad-feed.md for the exact steps. Automating access to a paid
product is a Terms-of-Service judgment call for you as the account holder.

Setup:
    copy scripts\\feeds\\milkroad_endpoints.sample.json scripts\\feeds\\milkroad_endpoints.json
    # edit milkroad_endpoints.json: paste the URL + field path for each indicator
    set MILKROAD_COOKIE=...      (your milkroad.com session cookie header value)
    python scripts\\feeds\\fetch_milkroad_indicators.py --debug   (first run: verify paths)
    python scripts\\feeds\\fetch_milkroad_indicators.py           (normal run)

Session cookies expire — when requests start failing, re-copy the cookie
value from DevTools and update MILKROAD_COOKIE.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/feeds -> trading-system
sys.path.insert(0, str(ROOT))

import requests

from trading_system.milkroad import load_milkroad, merge_milkroad, write_milkroad

CONFIG_PATH = Path(__file__).resolve().parent / "milkroad_endpoints.json"
SAMPLE_PATH = Path(__file__).resolve().parent / "milkroad_endpoints.sample.json"


def get_path(obj, path: str):
    """Walk a dotted path like 'data.score' or 'data.items.0.value' through
    nested dicts/lists (numeric segments index into lists). Returns None if
    any step is missing, rather than raising -- callers report that clearly."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"error: {CONFIG_PATH} not found.", file=sys.stderr)
        print(f"Copy {SAMPLE_PATH.name} to {CONFIG_PATH.name} in the same folder, "
              "then fill in the URL + value_path/label_path for each indicator "
              "(see docs/milkroad-feed.md for how to find them).", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(CONFIG_PATH.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                        help="print each endpoint's raw JSON, to help find value_path/label_path")
    args = parser.parse_args()

    cookie = os.environ.get("MILKROAD_COOKIE")
    if not cookie:
        print("error: set MILKROAD_COOKIE (your milkroad.com session cookie header value).",
              file=sys.stderr)
        return 2

    config = load_config()
    headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    indicators = {}
    today = date.today().isoformat()

    for key, spec in config.items():
        url = spec.get("url")
        if not url or "PASTE" in url:
            print(f"  {key}: no URL configured yet, skipping", file=sys.stderr)
            continue
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            print(f"  {key}: request failed ({exc})", file=sys.stderr)
            continue
        if resp.status_code != 200:
            print(f"  {key}: HTTP {resp.status_code} -- cookie may be stale, re-copy it",
                  file=sys.stderr)
            continue
        try:
            body = resp.json()
        except ValueError:
            print(f"  {key}: response wasn't JSON (got HTML? wrong endpoint or stale cookie)",
                  file=sys.stderr)
            continue
        if args.debug:
            print(f"--- {key} raw response (first 2000 chars) ---")
            print(json.dumps(body, indent=2)[:2000])
            print()
        value = get_path(body, spec["value_path"]) if spec.get("value_path") else None
        label = get_path(body, spec["label_path"]) if spec.get("label_path") else ""
        if value is None:
            print(f"  {key}: value_path '{spec.get('value_path')}' found nothing -- "
                  "re-run with --debug and inspect the raw JSON to fix the path",
                  file=sys.stderr)
            continue
        indicators[key] = {"value": value, "label": label or "", "as_of": today}
        print(f"  {key}: {value} ({label})")

    if not indicators:
        print("\nno indicators parsed -- see warnings above.", file=sys.stderr)
        return 1
    data = merge_milkroad(load_milkroad(), {
        "indicators": indicators, "source": "milkroad.com",
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })
    path = write_milkroad(data)
    print(f"\nwrote {len(indicators)} indicators -> {path}")
    print("run: python scripts/cockpit.py --config h1b   (to show them)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
