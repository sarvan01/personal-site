#!/usr/bin/env python3
"""Fetch the CBOE VIX (FRED series VIXCLS) into data/VIX_1d.csv for the U1
macro-risk-off regime test. FRED is free and needs no key.

Usage:
    python scripts/fetch_vix.py

After this, `python scripts/cockpit.py --config h1b` runs the U1 (VIX) and
U2 (crypto-stress) regime tests automatically alongside the event study.
VIX is forward-filled to a daily calendar so it aligns with crypto's
7-day-a-week data (markets are closed on weekends; the prior close carries).
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/research -> trading-system
sys.path.insert(0, str(ROOT))

import pandas as pd

from trading_system.macro import (
    VIX_SERIES,
    MacroError,
    fetch_fred,
    fetch_vix_cboe,
    fetch_vix_stooq,
)

# CBOE's official CSV first (authoritative, no key), then Stooq, then FRED.
# VIX is not on CoinStats (a crypto aggregator), so a traditional-markets
# source is required.
SOURCES = [
    ("CBOE", fetch_vix_cboe),
    ("Stooq", fetch_vix_stooq),
    ("FRED", lambda: fetch_fred(VIX_SERIES)),
]


def main() -> int:
    vix = None
    for name, fn in SOURCES:
        for attempt in range(2):
            try:
                vix = fn()
                print(f"VIX via {name}: {len(vix)} points")
                break
            except MacroError as exc:
                print(f"{name} attempt {attempt + 1} failed ({exc})", file=sys.stderr)
                time.sleep(2 ** attempt)
        if vix is not None:
            break
    if vix is None:
        print("error: all VIX sources unreachable. Usually transient — re-run "
              "scripts/fetch_vix.py in a minute.", file=sys.stderr)
        return 2
    # Reindex to a daily calendar and forward-fill weekends/holidays.
    daily = vix.reindex(
        pd.date_range(vix.index[0], vix.index[-1], freq="D", tz="UTC")
    ).ffill()
    daily.name = "close"
    path = ROOT / "data" / "VIX_1d.csv"
    daily.to_frame().rename_axis("date").to_csv(path)
    print(f"{len(daily)} days [{daily.index[0].date()} -> {daily.index[-1].date()}] -> {path}")
    print("\nNow run:  python scripts/cockpit.py --config h1b")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
