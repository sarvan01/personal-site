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


# Longest-first. "all" often exceeds a plan's allowed range (error 10012),
# so we step down to the longest window the plan accepts.
COINSTATS_PERIODS = ["all", "1y", "6m", "3m", "1m", "1w"]


def fetch_coinstats(coin_id: str, period: str, key: str) -> tuple[list, str]:
    """CoinStats -> ([[timestamp, price, ...], ...], period_used).

    If period == 'auto', try COINSTATS_PERIODS longest-first and return the
    first that yields data — so a plan that caps history still gets the most
    it can. Timestamps are unix seconds; points_to_frame detects the unit."""
    periods = COINSTATS_PERIODS if period == "auto" else [period]
    headers = {"X-API-KEY": key, "accept": "application/json"}
    last = None
    for per in periods:
        for attempt in range(3):
            resp = requests.get(
                f"{COINSTATS}/coins/{coin_id}/charts",
                params={"period": per}, headers=headers, timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                pts = data["data"] if isinstance(data, dict) and "data" in data else data
                if pts:
                    return pts, per
                last = f"empty for period={per}"
                break  # try a shorter window
            last = f"HTTP {resp.status_code} period={per}: {resp.text[:140]}"
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue  # rate-limited: retry same period
            break  # logical error (e.g. 10012): drop to a shorter period
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
    parser.add_argument("--period", default="auto",
                        help="CoinStats period: auto (longest that works) or all/1y/6m/3m/1m/1w")
    args = parser.parse_args()

    key = ""
    if args.source == "coinstats":
        key = os.environ.get("COINSTATS_API_KEY", "")
        if not key:
            print("error: set COINSTATS_API_KEY env var (or use --source coingecko)",
                  file=sys.stderr)
            return 2

    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    short_cover = []
    for sym, coin_id in BASKET.items():
        print(f"fetching {sym} ({coin_id}) via {args.source} ...")
        if args.source == "coinstats":
            points, used = fetch_coinstats(coin_id, args.period, key)
        else:
            points, used = fetch_coingecko(coin_id, args.days), args.days
        df = points_to_frame(points)
        path = ROOT / "data" / f"PRIV_{sym}_1d.csv"
        df.to_csv(path)
        first, last = df.index[0].date(), df.index[-1].date()
        print(f"  {len(df)} days [{first} -> {last}] (window={used}) -> {path}")
        # The oldest pre-registered event is 2022-08 (Tornado Cash). Flag any
        # coin whose history starts after 2022 — those events can't be tested.
        if df.index[0].year > 2022:
            short_cover.append(f"{sym} (from {first})")
        time.sleep(1)

    if short_cover:
        print("\nNOTE: limited history for: " + ", ".join(short_cover))
        print("Events before those dates won't be testable for those coins.")
        print("For full multi-year history, try: python scripts/fetch_privacy.py --source coingecko")

    print("\nDone. Now run:  python scripts/cockpit.py --config h1b")
    print("The event-study verdict will appear in out/cockpit.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
