#!/usr/bin/env python3
"""Fetch privacy-coin daily prices into data/PRIV_<SYM>_1d.csv for the
Railgun / privacy event study (H2).

Two sources:
  --source coinstats   CoinStats Open API (needs COINSTATS_API_KEY env var;
                       use this if you have CoinStats Premium — more reliable)
  --source coingecko   CoinGecko public API (free, no key, but rate-limited)

Privacy coins are mostly absent or delisted on Binance (XMR delisted Feb
2024), so this uses a market-data aggregator instead. After running, the
cockpit picks up the CSVs and runs the event study automatically (it also
needs research/privacy_events.csv).

Usage:
    setx COINSTATS_API_KEY "your_key"        # once, then open a new terminal
    python scripts/fetch_privacy.py --source coinstats
    python scripts/fetch_privacy.py --source coingecko --days 1500
"""

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import requests

# Symbol -> aggregator coin id. These ids are the same on CoinStats and
# CoinGecko for this basket. If one 404s, open the coin's page on the source
# site and copy the id from its URL. Edit BEFORE looking at returns.
BASKET = {
    "XMR": "monero",
    "ZEC": "zcash",
    "SCRT": "secret",
    "RAIL": "railgun",
    "DASH": "dash",
}

COINGECKO = "https://api.coingecko.com/api/v3"
COINSTATS = "https://openapiv1.coinstats.app"


def fetch_coingecko(coin_id: str, days: str) -> list:
    """CoinGecko -> [[ms_timestamp, price], ...] (daily auto for days > 90)."""
    last = None
    for attempt in range(4):
        resp = requests.get(
            f"{COINGECKO}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["prices"]
        last = f"HTTP {resp.status_code}: {resp.text[:160]}"
        time.sleep(2 ** attempt)
    raise SystemExit(f"CoinGecko failed for {coin_id}: {last}")


def fetch_coinstats(coin_id: str, period: str, key: str) -> list:
    """CoinStats -> [[timestamp, price, ...], ...]. Timestamps are unix
    seconds; points_to_frame detects the unit either way."""
    last = None
    for attempt in range(4):
        resp = requests.get(
            f"{COINSTATS}/coins/{coin_id}/charts",
            params={"period": period},
            headers={"X-API-KEY": key, "accept": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Bare array per the docs; tolerate a {"data": [...]} wrapper too.
            return data["data"] if isinstance(data, dict) and "data" in data else data
        last = f"HTTP {resp.status_code}: {resp.text[:160]}"
        time.sleep(2 ** attempt)
    raise SystemExit(f"CoinStats failed for {coin_id}: {last}")


def points_to_frame(points: list) -> pd.DataFrame:
    """[[ts, price, ...], ...] -> DataFrame indexed by normalized UTC date
    with a 'close' column, one row per day. Detects whether timestamps are
    seconds or milliseconds so both sources work."""
    ts = [p[0] for p in points]
    unit = "ms" if (ts and max(ts) > 1e11) else "s"
    idx = pd.to_datetime(ts, unit=unit, utc=True).normalize()
    s = pd.Series([float(p[1]) for p in points], index=idx, name="close")
    s = s[~s.index.duplicated(keep="last")]
    df = s.to_frame()
    df.index.name = "date"
    return df


# Back-compat alias (older imports/tests used prices_to_frame for CoinGecko).
prices_to_frame = points_to_frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["coinstats", "coingecko"], default="coinstats")
    parser.add_argument("--days", default="max", help="CoinGecko history length")
    parser.add_argument("--period", default="all", help="CoinStats period (all/1y/...)")
    args = parser.parse_args()

    key = ""
    if args.source == "coinstats":
        key = os.environ.get("COINSTATS_API_KEY", "")
        if not key:
            print("error: set COINSTATS_API_KEY env var (or use --source coingecko)",
                  file=sys.stderr)
            return 2

    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    for sym, coin_id in BASKET.items():
        print(f"fetching {sym} ({coin_id}) via {args.source} ...")
        if args.source == "coinstats":
            points = fetch_coinstats(coin_id, args.period, key)
        else:
            points = fetch_coingecko(coin_id, args.days)
        df = points_to_frame(points)
        path = ROOT / "data" / f"PRIV_{sym}_1d.csv"
        df.to_csv(path)
        print(f"  {len(df)} days -> {path}")
        time.sleep(1)

    print("\nDone. Now run:  python scripts/cockpit.py --config h1b")
    print("The event-study verdict will appear in out/cockpit.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
