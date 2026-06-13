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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from trading_system.macro import VIX_SERIES, MacroError, fetch_fred


def main() -> int:
    try:
        vix = fetch_fred(VIX_SERIES)
    except MacroError as exc:
        print(f"error: {exc}", file=sys.stderr)
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
