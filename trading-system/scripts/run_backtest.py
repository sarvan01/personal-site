#!/usr/bin/env python3
"""Run the pre-declared trend grid + walk-forward validation.

Usage:
    python scripts/run_backtest.py             # uses cached real data in data/
    python scripts/run_backtest.py --synthetic # offline demo on synthetic data

Pass criterion (pre-registered, report section 8): positive net return and
Sharpe > 0.7 across the WHOLE lookback grid, max drawdown < 35%. The script
prints PASS/FAIL against that criterion; it does not move the goalposts.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from trading_system.backtest import run_grid, walk_forward
from trading_system.config import DEFAULT
from trading_system.data import DataError, load_klines, synthetic_klines

PASS_MIN_SHARPE = 0.7
PASS_MAX_DD = -0.35


def load_universe(synthetic: bool) -> dict[str, pd.DataFrame]:
    if synthetic:
        print("== SYNTHETIC DATA (pipeline demo, not a real backtest) ==\n")
        return {
            "BTCUSDT": synthetic_klines(seed=7),
            "ETHUSDT": synthetic_klines(seed=13),
        }
    try:
        return {sym: load_klines(sym) for sym in DEFAULT.universe}
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("hint: run scripts/fetch_data.py, or use --synthetic", file=sys.stderr)
        raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()

    ohlc = load_universe(args.synthetic)
    cfg = DEFAULT

    print("Lookback grid (net of costs):")
    grid = run_grid(ohlc, cfg)
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(grid.to_string(), "\n")

    ok = bool(
        (grid["total_return"] > 0).all()
        and (grid["sharpe"] > PASS_MIN_SHARPE).all()
        and (grid["max_drawdown"] > PASS_MAX_DD).all()
    )
    print(
        f"Pre-registered criterion (all lookbacks: return>0, Sharpe>{PASS_MIN_SHARPE},"
        f" maxDD<{-PASS_MAX_DD:.0%}): {'PASS' if ok else 'FAIL'}\n"
    )

    print("Walk-forward (2-year windows, lookback=100):")
    wf = walk_forward(ohlc, cfg, lookback=100)
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(wf.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
