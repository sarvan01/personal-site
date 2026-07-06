#!/usr/bin/env python3
"""Battle-test battery: stress scenarios + Monte Carlo forward distribution.

Runs the H1b system through deliberately hostile conditions and writes
out/stress_report.json (picked up by the cockpit on its next run):

  base          -- full-history backtest metrics (the reference point)
  flash_crash   -- a -40% single day appended to every symbol: does the
                   breaker contain it, and what does the worst day cost?
  worst_year    -- the worst rolling ~1y window in the sample (what living
                   through the bad regime actually felt like)
  ragged_data   -- random missing bars for one symbol: pipeline must still
                   run and produce finite metrics
  monte_carlo   -- block-bootstrap 1y-forward distribution: return
                   percentiles + probability of hitting each breaker level

Usage:
    python scripts/stress_test.py              # cached real data
    python scripts/stress_test.py --synthetic  # offline demo
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from trading_system.backtest import run_backtest
from trading_system.config import CONFIGS
from trading_system.data import DataError, load_klines, synthetic_klines
from trading_system.indicators import TRADING_DAYS
from trading_system.montecarlo import forward_distribution

REPORT_PATH = ROOT / "out" / "stress_report.json"


def load_universe(synthetic: bool, cfg):
    if synthetic:
        return {s: synthetic_klines(days=1500, seed=i * 7 + 3)
                for i, s in enumerate(cfg.universe)}
    return {sym: load_klines(sym) for sym in cfg.universe}


def _metrics_subset(m: dict) -> dict:
    keys = ("total_return", "cagr", "sharpe", "max_drawdown", "ann_vol")
    return {k: round(m[k], 4) for k in keys if k in m}


def scenario_flash_crash(ohlc, cfg, lookback) -> dict:
    """Append one -40% day to every symbol and measure the damage."""
    crashed = {}
    for sym, df in ohlc.items():
        last = df.iloc[-1]
        day = df.index[-1] + pd.Timedelta(days=1)
        row = pd.DataFrame({
            "open": [last["close"]],
            "high": [last["close"]],
            "low": [last["close"] * 0.55],
            "close": [last["close"] * 0.60],
            "volume": [last["volume"]],
        }, index=pd.DatetimeIndex([day], name="date"))
        crashed[sym] = pd.concat([df, row])
    base = run_backtest(ohlc, cfg, lookback)
    stressed = run_backtest(crashed, cfg, lookback)
    worst_day = float(stressed.equity.pct_change().min())
    crash_day_loss = float(
        stressed.equity.iloc[-1] / stressed.equity.iloc[-2] - 1.0)
    return {
        "scenario": "every symbol -40% in one day",
        "portfolio_loss_on_crash_day": round(crash_day_loss, 4),
        "worst_single_day_in_series": round(worst_day, 4),
        "gross_exposure_going_in": round(
            float(stressed.weights.iloc[-2].sum()), 4),
        "note": ("loss is bounded by gross exposure going into the crash; "
                 "the -15% breaker then flattens the book on the next bar"),
        "base_final_equity": round(float(base.equity.iloc[-1]), 2),
        "stressed_final_equity": round(float(stressed.equity.iloc[-1]), 2),
    }


def scenario_worst_year(ohlc, cfg, lookback) -> dict:
    """Worst rolling ~1y net-return window of the whole backtest."""
    res = run_backtest(ohlc, cfg, lookback)
    eq = res.equity
    window = min(TRADING_DAYS, len(eq) - 1)
    rolling = eq / eq.shift(window) - 1.0
    worst_end = rolling.idxmin()
    worst_ret = float(rolling.min())
    start = worst_end - pd.Timedelta(days=window)
    return {
        "scenario": f"worst rolling {window}-day window in sample",
        "window": f"{start.date()} -> {worst_end.date()}",
        "net_return": round(worst_ret, 4),
        "note": "this is what the bad regime felt like; expect it again",
    }


def scenario_ragged_data(ohlc, cfg, lookback) -> dict:
    """Randomly delete 5 bars from one symbol; the run must survive."""
    rng = np.random.default_rng(42)
    sym = list(ohlc)[-1]
    df = ohlc[sym]
    drop = rng.choice(len(df) - 50, size=5, replace=False) + 25
    ragged = dict(ohlc)
    ragged[sym] = df.drop(df.index[drop])
    res = run_backtest(ragged, cfg, lookback)
    m = res.metrics
    finite = all(np.isfinite(v) for k, v in m.items()
                 if isinstance(v, float))
    return {
        "scenario": f"5 random missing bars in {sym}",
        "pipeline_survived": True,
        "metrics_finite": bool(finite),
        **_metrics_subset(m),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--config", choices=sorted(CONFIGS), default="h1b")
    parser.add_argument("--lookback", type=int, default=100)
    parser.add_argument("--paths", type=int, default=2000)
    args = parser.parse_args()
    cfg = CONFIGS[args.config]

    try:
        ohlc = load_universe(args.synthetic, cfg)
    except (DataError, FileNotFoundError) as exc:
        print(f"error: {exc}\nhint: run scripts/fetch_data.py --config {args.config}, "
              "or use --synthetic", file=sys.stderr)
        return 2

    print(f"config: {args.config} | data: "
          f"{'SYNTHETIC (demo)' if args.synthetic else 'real'} | "
          f"lookback: {args.lookback}\n")

    base = run_backtest(ohlc, cfg, args.lookback)
    report = {
        "config": args.config,
        "data_mode": "synthetic" if args.synthetic else "real",
        "base": _metrics_subset(base.metrics),
    }

    print("[1/4] flash crash (-40% day) ...")
    report["flash_crash"] = scenario_flash_crash(ohlc, cfg, args.lookback)
    print(f"      crash-day portfolio loss: "
          f"{report['flash_crash']['portfolio_loss_on_crash_day']:+.2%} "
          f"(gross going in: {report['flash_crash']['gross_exposure_going_in']:.1%})")

    print("[2/4] worst historical year ...")
    report["worst_year"] = scenario_worst_year(ohlc, cfg, args.lookback)
    print(f"      {report['worst_year']['window']}: "
          f"{report['worst_year']['net_return']:+.2%}")

    print("[3/4] ragged data (missing bars) ...")
    report["ragged_data"] = scenario_ragged_data(ohlc, cfg, args.lookback)
    print(f"      survived: {report['ragged_data']['pipeline_survived']}, "
          f"metrics finite: {report['ragged_data']['metrics_finite']}")

    print(f"[4/4] Monte Carlo ({args.paths} bootstrap years) ...")
    mc = forward_distribution(base.equity, n_paths=args.paths)
    report["monte_carlo"] = mc
    r = mc["return_1y"]
    print(f"      1y return p5/p50/p95: {r['p5']:+.1%} / {r['p50']:+.1%} / {r['p95']:+.1%}")
    print(f"      P(positive year): {mc['prob_positive_year']:.0%} | "
          f"P(hit -10% breaker): {mc['prob_dd_exceeds_10pct']:.0%} | "
          f"P(hit -15% breaker): {mc['prob_dd_exceeds_15pct']:.0%}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nreport -> {REPORT_PATH}")
    print("(the cockpit will show it on its next run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
