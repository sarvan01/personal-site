#!/usr/bin/env python3
"""DIAGNOSTIC (read-only) -- probe Milk Road's rhc.milkroad.com widget
endpoints to see whether they're reachable without login and what format
they return. Does NOT write to data/milkroad.json.

These URLs were found embedded as <iframe src="..."> in milkroad.com/data/'s
page source. Cross-origin iframes don't automatically carry the parent
site's login cookie, so there's a real chance these work with zero auth --
this script tests that hypothesis across all of them in one shot with a
browser-like User-Agent and Referer header (in case they check for embedding
from milkroad.com), and reports what each one actually returns.

Usage:
    python scripts/feeds/probe_milkroad_iframes.py
    python scripts/feeds/probe_milkroad_iframes.py --full   (print full body, not just a snippet)
"""

import argparse
import sys

import requests

IFRAMES = {
    "fear_greed": "https://rhc.milkroad.com/iframe/crypto/fear-greed",
    "btc_dominance": "https://rhc.milkroad.com/iframe/crypto/btc-dominance",
    "crypto_vs_tradfi": "https://rhc.milkroad.com/iframe/crypto/crypto-vs-tradfi",
    "rwa_categories": "https://rhc.milkroad.com/iframe/crypto/rwa-categories",
    "pmi": "https://rhc.milkroad.com/iframe/macro/pmi",
    "cpi_yoy": "https://rhc.milkroad.com/iframe/macro/cpi-yoy",
    "dxy": "https://rhc.milkroad.com/iframe/macro/dxy-indicator",
    "us10y": "https://rhc.milkroad.com/iframe/macro/us10y-indicator",
    "gold": "https://rhc.milkroad.com/iframe/macro/gold-indicator",
    "spy": "https://rhc.milkroad.com/iframe/macro/spy-indicator",
    "nasdaq": "https://rhc.milkroad.com/iframe/macro/nasdaq-indicator",
    "btc24h": "https://rhc.milkroad.com/iframe/macro/btc24h-indicator",
    "eth24h": "https://rhc.milkroad.com/iframe/macro/eth24h-indicator",
    "sol24h": "https://rhc.milkroad.com/iframe/macro/sol24h-indicator",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://milkroad.com/",
    "Accept": "text/html,application/json,*/*",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="print full response body")
    args = parser.parse_args()

    for key, url in IFRAMES.items():
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as exc:
            print(f"{key:20} FAILED   {exc}")
            continue
        ctype = resp.headers.get("content-type", "?")
        body = resp.text if args.full else resp.text[:200].replace("\n", " ")
        print(f"{key:20} HTTP {resp.status_code}  {ctype:30}")
        print(f"  {body}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
