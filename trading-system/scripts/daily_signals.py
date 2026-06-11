#!/usr/bin/env python3
"""Daily signal run: regime, trend signals, carry status -> out/status.{json,html}.

Usage:
    python scripts/daily_signals.py             # cached real data
    python scripts/daily_signals.py --synthetic # offline demo

Intended as a daily cron job after the 00:00 UTC close. Generates signals
and the one-page dashboard only — order placement is deliberately absent.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from trading_system.carry import current_status
from trading_system.config import DEFAULT
from trading_system.data import (
    DataError,
    load_funding,
    load_klines,
    synthetic_funding,
    synthetic_klines,
)
from trading_system.regime import classify
from trading_system.report import write_status
from trading_system.risk import asset_weight
from trading_system.indicators import realized_vol
from trading_system.strategy import stop_distance, trend_signal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--lookback", type=int, default=100)
    args = parser.parse_args()
    cfg = DEFAULT

    if args.synthetic:
        ohlc = {"BTCUSDT": synthetic_klines(seed=7), "ETHUSDT": synthetic_klines(seed=13)}
        funding = synthetic_funding()
    else:
        try:
            ohlc = {sym: load_klines(sym) for sym in cfg.universe}
            funding = load_funding(cfg.benchmark)
        except (DataError, FileNotFoundError) as exc:
            print(f"error: {exc}\nhint: run scripts/fetch_data.py, or use --synthetic", file=sys.stderr)
            return 2

    bench = ohlc[cfg.benchmark]["close"]
    regime_df = classify(bench, cfg.regime)
    regime_today = {
        "state": regime_df["regime"].iloc[-1],
        "exposure_multiplier": float(regime_df["multiplier"].iloc[-1]),
        "as_of": str(regime_df.index[-1].date()),
    }

    signals = {}
    for sym, df in ohlc.items():
        sig = float(trend_signal(df["close"], args.lookback, cfg.trend.exit_divisor).iloc[-1])
        stop = float(stop_distance(df["high"], df["low"], df["close"], cfg.trend).iloc[-1])
        vol = float(realized_vol(df["close"], cfg.regime.vol_window).iloc[-1])
        price = float(df["close"].iloc[-1])
        w = asset_weight(sig, vol, price, stop, cfg.risk) * regime_today["exposure_multiplier"]
        signals[sym] = {
            "signal": bool(sig),
            "close": price,
            "stop_distance": stop,
            "target_weight": w,
        }

    carry = current_status(funding, cfg.carry)
    risk = {
        "per_trade_risk": cfg.risk.per_trade_risk,
        "max_asset_weight": cfg.risk.max_asset_weight,
        "max_gross": cfg.risk.max_gross,
        "circuit_breakers": f"-{cfg.risk.dd_half_size:.0%} half size / -{cfg.risk.dd_go_flat:.0%} flat",
    }

    json_path, html_path = write_status(regime_today, signals, carry, risk)
    print(f"wrote {json_path}\nwrote {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
