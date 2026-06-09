#!/usr/bin/env python3
"""Download daily klines and funding history for the universe into data/.

Usage:
    python scripts/fetch_data.py [--start 2017-01-01]

Requires network access to Binance (api.binance.com / fapi.binance.com or
the data-api.binance.vision mirror). Run from your own machine if your
environment blocks these hosts.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.config import DEFAULT
from trading_system.data import fetch_daily_klines, fetch_funding, save_csv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2017-01-01")
    args = parser.parse_args()

    for symbol in DEFAULT.universe:
        print(f"fetching {symbol} daily klines from {args.start} ...")
        klines = fetch_daily_klines(symbol, args.start)
        path = save_csv(klines, symbol, "1d")
        print(f"  {len(klines)} bars -> {path}")

        print(f"fetching {symbol} funding history ...")
        funding = fetch_funding(symbol, max(args.start, "2020-01-01"))
        path = save_csv(funding, symbol, "funding")
        print(f"  {len(funding)} periods -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
