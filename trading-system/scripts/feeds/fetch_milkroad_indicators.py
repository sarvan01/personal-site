#!/usr/bin/env python3
"""TEMPLATE — pull Milk Road macro-index / macro-pulse / crypto-pulse into
data/milkroad.json (CONTEXT feed, NOT a trading signal).

WARNING: Milk Road has no public API, and these pages are premium content
behind your login. Automated scraping of a paid product may violate Milk Road's
Terms of Service — proceed only if you are comfortable it is allowed for your
account. This is a skeleton: you must supply the auth and fill in scrape_value()
for your account (the pages render client-side, so the cleanest route is often
the underlying JSON endpoint visible in your browser's Network tab, not the HTML).

Setup:
    set MILKROAD_COOKIE=...      (your milkroad.com session cookie)
    python scripts/feeds/fetch_milkroad_indicators.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/feeds -> trading-system
sys.path.insert(0, str(ROOT))

import requests

from trading_system.milkroad import load_milkroad, merge_milkroad, write_milkroad

PAGES = {
    "macro_index": "https://milkroad.com/data/macro-index/",
    "macro_pulse": "https://milkroad.com/data/macro-pulse/",
    "crypto_pulse": "https://milkroad.com/data/crypto-pulse/",
}


def scrape_value(key: str, html: str) -> dict:
    """Return {"value": <0-100>, "label": "...", "as_of": "YYYY-MM-DD"}.

    TODO: implement for your account. Inspect the page in your browser's
    Network tab — Milk Road likely serves the number from a JSON endpoint you
    can hit directly with your session cookie, which is far more robust than
    parsing rendered HTML.
    """
    raise NotImplementedError(
        f"{key}: fill in scrape_value() — find the JSON endpoint or selector")


def main() -> int:
    cookie = os.environ.get("MILKROAD_COOKIE")
    if not cookie:
        print("error: set MILKROAD_COOKIE (your milkroad.com session cookie).",
              file=sys.stderr)
        return 2
    headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0"}
    indicators = {}
    for key, url in PAGES.items():
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            print(f"  {key}: request failed ({exc})", file=sys.stderr)
            continue
        if resp.status_code != 200:
            print(f"  {key}: HTTP {resp.status_code}", file=sys.stderr)
            continue
        try:
            indicators[key] = scrape_value(key, resp.text)
        except NotImplementedError as exc:
            print(f"  {exc}", file=sys.stderr)

    if not indicators:
        print("no indicators parsed — complete scrape_value() first.", file=sys.stderr)
        return 1
    data = merge_milkroad(load_milkroad(), {"indicators": indicators, "source": "milkroad.com"})
    path = write_milkroad(data)
    print(f"wrote {len(indicators)} indicators -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
