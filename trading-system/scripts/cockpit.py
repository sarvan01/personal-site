#!/usr/bin/env python3
"""Build the cockpit: run every analysis the data allows and render the
single-page dashboard at out/cockpit.html (plus out/status.json and a
go/no-go memo at out/decision_memo.md).

Usage:
    python scripts/cockpit.py             # cached real data (data/*.csv)
    python scripts/cockpit.py --synthetic # offline end-to-end demo

Intended as the one daily command (cron candidate). No live orders.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from trading_system.backtest import run_grid, walk_forward
from trading_system.carry import current_status
from trading_system.cockpit import build_cockpit
from trading_system.config import CONFIGS
from trading_system.data import (
    DataError,
    load_funding,
    load_klines,
    synthetic_funding,
    synthetic_klines,
)
from trading_system.data import _utc_index
from trading_system.event_study import run_event_study, synthetic_study_data
from trading_system.indicators import realized_vol
from trading_system.macro import macro_risk_off, synthetic_macro
from trading_system.paper import PaperAccount
from trading_system.regime import classify
from trading_system.risk import asset_weight
from trading_system.strategy import stop_distance, trend_signal

PASS_MIN_SHARPE = 0.7
PASS_MAX_DD = -0.35
EVENTS_CSV = ROOT / "research" / "privacy_events.csv"


def load_inputs(synthetic: bool, cfg):
    if synthetic:
        ohlc = {"BTCUSDT": synthetic_klines(seed=7), "ETHUSDT": synthetic_klines(seed=13)}
        funding = synthetic_funding()
        dxy, ry, stables = synthetic_macro()
        basket, bench, events = synthetic_study_data(effect=0.0)
        return ohlc, funding, (dxy, ry, stables), (basket, bench, events)
    ohlc = {sym: load_klines(sym) for sym in cfg.universe}
    funding = load_funding(cfg.benchmark)
    macro = (None, None, None)  # fetch via trading_system.macro when online
    study = None  # needs privacy-basket price CSVs in data/ + events CSV
    priv_files = sorted((ROOT / "data").glob("PRIV_*_1d.csv"))
    if priv_files and EVENTS_CSV.exists():
        cols = {}
        for f in priv_files:
            pdf = pd.read_csv(f, index_col=0)
            pdf.index = _utc_index(pdf.index)
            cols[f.stem] = pdf["close"]
        basket = pd.DataFrame(cols)
        events = pd.read_csv(EVENTS_CSV)["date"].tolist()
        study = (basket, ohlc[cfg.benchmark]["close"], events)
    return ohlc, funding, macro, study


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--config", choices=sorted(CONFIGS), default="default")
    parser.add_argument("--lookback", type=int, default=100)
    parser.add_argument("--perms", type=int, default=2000)
    parser.add_argument(
        "--replay",
        type=int,
        default=60,
        help="on a fresh ledger, replay the last N days through the paper "
        "account using each day's own signals (default 60)",
    )
    args = parser.parse_args()
    cfg = CONFIGS[args.config]

    try:
        ohlc, funding, macro, study = load_inputs(args.synthetic, cfg)
    except (DataError, FileNotFoundError) as exc:
        print(f"error: {exc}\nhint: run scripts/fetch_data.py, or use --synthetic", file=sys.stderr)
        return 2

    # --- regime (with macro composite when available) -----------------------
    bench = ohlc[cfg.benchmark]["close"]
    risk_off = macro_risk_off(*macro, index=bench.index) if any(m is not None for m in macro) else None
    regime_df = classify(bench, cfg.regime, macro_risk_off=risk_off)
    regime = {
        "state": regime_df["regime"].iloc[-1],
        "exposure_multiplier": float(regime_df["multiplier"].iloc[-1]),
        "macro_composite": "active" if risk_off is not None else "unavailable (offline)",
        "as_of": str(regime_df.index[-1].date()),
    }

    # --- sleeve A signals ----------------------------------------------------
    signals = {}
    for sym, df in ohlc.items():
        sig = float(trend_signal(df["close"], args.lookback, cfg.trend.exit_divisor).iloc[-1])
        stop = float(stop_distance(df["high"], df["low"], df["close"], cfg.trend).iloc[-1])
        vol = float(realized_vol(df["close"], cfg.regime.vol_window).iloc[-1])
        price = float(df["close"].iloc[-1])
        w = asset_weight(sig, vol, price, stop, cfg.risk) * regime["exposure_multiplier"]
        signals[sym] = {"signal": bool(sig), "close": price, "target_weight": w}

    # --- sleeve B ------------------------------------------------------------
    carry = current_status(funding, cfg.carry)

    # --- paper account step --------------------------------------------------
    # Replay: walk the last N days through the ledger using each day's own
    # signal/vol/stop values (identical math to a live daily run, replayed).
    account = PaperAccount()
    n_days = args.replay if account.state["last_date"] is None else 1
    sig_series, stop_series, vol_series = {}, {}, {}
    for sym, df in ohlc.items():
        sig_series[sym] = trend_signal(df["close"], args.lookback, cfg.trend.exit_divisor)
        stop_series[sym] = stop_distance(df["high"], df["low"], df["close"], cfg.trend)
        vol_series[sym] = realized_vol(df["close"], cfg.regime.vol_window)
    for i in range(-n_days, 0):
        day = bench.index[i]
        closes = {s: float(df["close"].loc[day]) for s, df in ohlc.items()}
        prev_closes = {
            s: float(df["close"].iloc[df.index.get_loc(day) - 1]) for s, df in ohlc.items()
        }
        mult = float(regime_df["multiplier"].loc[day])
        targets = {
            s: asset_weight(
                float(sig_series[s].loc[day]),
                float(vol_series[s].loc[day]),
                closes[s],
                float(stop_series[s].loc[day]),
                cfg.risk,
            )
            * mult
            for s in ohlc
        }
        account.step(str(day.date()), closes, prev_closes, targets, cfg)
    account.save()

    # --- backtest grid + walk-forward ----------------------------------------
    grid = run_grid(ohlc, cfg)
    gate = bool(
        (grid["total_return"] > 0).all()
        and (grid["sharpe"] > PASS_MIN_SHARPE).all()
        and (grid["max_drawdown"] > PASS_MAX_DD).all()
    )
    wf = walk_forward(ohlc, cfg, lookback=args.lookback)
    backtest = {
        "pass": gate,
        "grid": grid.round(3).reset_index().to_dict("records"),
        "walk_forward": wf.round(3).to_dict("records"),
    }

    # --- event study ----------------------------------------------------------
    event_study = None
    if study is not None:
        basket, study_bench, events = study
        result = run_event_study(basket, study_bench, events, n_perm=args.perms)
        event_study = result.to_dict()

    # --- outputs ---------------------------------------------------------------
    risk = {
        "per_trade_risk": cfg.risk.per_trade_risk,
        "max_asset_weight": cfg.risk.max_asset_weight,
        "max_gross": cfg.risk.max_gross,
        "target_vol": cfg.risk.target_vol,
        "circuit_breakers": f"-{cfg.risk.dd_half_size:.0%} half / -{cfg.risk.dd_go_flat:.0%} flat",
    }
    equity_history = [h["equity"] for h in account.state["history"]]
    path = build_cockpit(
        regime=regime,
        signals=signals,
        carry=carry,
        risk=risk,
        paper=account.summary(),
        equity_history=equity_history,
        backtest=backtest,
        event_study=event_study,
        reconciliation=account.reconciliation(),
        data_mode="synthetic" if args.synthetic else "real",
    )

    status = {
        "regime": regime,
        "signals": signals,
        "carry": carry,
        "risk": risk,
        "paper": account.summary(),
        "backtest_gate": "PASS" if gate else "FAIL",
        "data_mode": "synthetic" if args.synthetic else "real",
    }
    (ROOT / "out" / "status.json").write_text(json.dumps(status, indent=2, default=str))

    memo = [
        "# Go / No-Go Decision Memo",
        "",
        f"- Data mode: {'SYNTHETIC (not decision-grade)' if args.synthetic else 'real'}",
        f"- Pre-registered backtest gate: {'PASS' if gate else 'FAIL'}",
        f"- Paper-trading days recorded: {len(equity_history)} (need >= 20 clean days)",
        f"- Cost reconciliation fills observed: {account.reconciliation()['n_with_observed_costs']}",
        "",
        "Live capital requires ALL of: real-data gate PASS, 4 clean paper weeks,",
        "observed costs within 1.5x of assumptions, zero manual overrides.",
        "Decision: GO" if gate and not args.synthetic and len(equity_history) >= 20 else "Decision: NO-GO (conditions above not yet met)",
    ]
    (ROOT / "out" / "decision_memo.md").write_text("\n".join(memo) + "\n")

    print(f"cockpit  -> {path}")
    print(f"status   -> {ROOT / 'out' / 'status.json'}")
    print(f"memo     -> {ROOT / 'out' / 'decision_memo.md'}")
    print(f"backtest gate: {'PASS' if gate else 'FAIL'} | regime: {regime['state']} | carry: {carry['signal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
