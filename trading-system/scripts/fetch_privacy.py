#!/usr/bin/env python3
"""Fetch privacy-coin daily prices into data/PRIV_<SYM>_1d.csv for the
Railgun / privacy event study (H2).

Source: CoinGecko public API (free, no key). Privacy coins are mostly absent
or delisted on Binance (XMR delisted Feb 2024), so this uses a separate
source. After running this, `python scripts/cockpit.py` picks up the CSVs
and runs the event study automatically (it also needs research/privacy_events.csv).

Usage:
    python scripts/fetch_privacy.py            # full history
    python scripts/fetch_privacy.py --days 1500
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import requests

# Symbol -> CoinGecko id. Edit BEFORE looking at returns if you change the
# basket, and mirror any change in research/privacy_events.csv reasoning.
BASKET = {
    "XMR": "monero",
    "ZEC": "zcash",
    "SCRT": "secret",
    "RAIL": "railgun",
    "DASH": "dash",
}
CG = "https://api.coingecko.com/api/v3"


def fetch_prices(coin_id: str, days: str) -> list:
    """Return CoinGecko [[ms_timestamp, price], ...]. Daily granularity is
    automatic for ranges > 90 days, so we omit the paid 'interval' param."""
    last = None
    for attempt in range(4):
        resp = requests.get(
            f"{CG}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["prices"]
        last = f"HTTP {resp.status_code}: {resp.text[:160]}"
        time.sleep(2 ** attempt)
    raise SystemExit(f"CoinGecko failed for {coin_id}: {last}")


def prices_to_frame(prices: list) -> pd.DataFrame:
    """[[ms, price], ...] -> DataFrame indexed by normalized UTC date with a
    'close' column, de-duplicated to one row per day (aligns with Binance
    klines, which are normalized the same way)."""
    idx = pd.to_datetime([p[0] for p in prices], unit="ms", utc=True).normalize()
    s = pd.Series([p[1] for p in prices], index=idx, name="close")
    s = s[~s.index.duplicated(keep="last")]
    df = s.to_frame()
    df.index.name = "date"
    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", default="max", help="history length, e.g. 1500 or 'max'")
    args = parser.parse_args()

    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    for sym, coin_id in BASKET.items():
        print(f"fetching {sym} ({coin_id}) ...")
        df = prices_to_frame(fetch_prices(coin_id, args.days))
        path = ROOT / "data" / f"PRIV_{sym}_1d.csv"
        df.to_csv(path)
        print(f"  {len(df)} days -> {path}")
        time.sleep(2)  # be polite to the free endpoint

    print("\nDone. Now run:  python scripts/cockpit.py --config h1b")
    print("The event-study verdict will appear in out/cockpit.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
