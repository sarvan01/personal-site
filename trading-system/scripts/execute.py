#!/usr/bin/env python3
"""Translate the latest daily signals into orders.

SAFE BY DEFAULT. With no flags this runs DRY: it prints exactly what it
WOULD trade and simulates fills against a local balance file — no network,
no real orders.

Usage:
    python scripts/execute.py                      # DRY preview (default)
    python scripts/execute.py --venue testnet      # real orders on Binance TESTNET (play money)
    python scripts/execute.py --venue live --i-understand-live   # real money (also needs ALLOW_LIVE_TRADING=yes)

Testnet/live need BINANCE_KEY and BINANCE_SECRET env vars. Testnet keys are
free at https://testnet.binance.vision. Live additionally requires the
ALLOW_LIVE_TRADING=yes env var — two independent gates, on purpose.

Every order is checked against the risk policy and scaled by the circuit
breaker before it is sent. Run this only AFTER the paper-trading phase has
produced a GO in out/decision_memo.md.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trading_system.config import CONFIGS
from trading_system.data import DataError, load_klines
from trading_system.execution import (
    ExecutionError,
    Executor,
    Venue,
    make_broker,
    observed_cost_bps,
)
from trading_system.paper import PaperAccount
from trading_system.signals import latest_targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venue", choices=[v.value for v in Venue], default="dry")
    parser.add_argument("--config", choices=sorted(CONFIGS), default="h1b")
    parser.add_argument("--lookback", type=int, default=100)
    parser.add_argument("--i-understand-live", action="store_true",
                        help="second gate required for --venue live")
    parser.add_argument("--execute", action="store_true",
                        help="actually place orders (default is preview only)")
    args = parser.parse_args()
    cfg = CONFIGS[args.config]
    venue = Venue(args.venue)

    try:
        ohlc = {sym: load_klines(sym) for sym in cfg.universe}
    except (DataError, FileNotFoundError) as exc:
        print(f"error: {exc}\nhint: run scripts/fetch_data.py --config {args.config} first",
              file=sys.stderr)
        return 2

    targets_full, regime = latest_targets(ohlc, cfg, args.lookback)
    targets = {s: v["target_weight"] for s, v in targets_full.items()}
    prices = {s: v["close"] for s, v in targets_full.items()}

    # Honor the persisted circuit-breaker state from the paper account.
    account = PaperAccount()
    dd = account.summary()["drawdown"]
    scale = 1.0
    if dd <= -cfg.risk.dd_go_flat or account.state.get("cooldown_left", 0) > 0:
        scale = 0.0
    elif dd <= -cfg.risk.dd_half_size:
        scale = 0.5

    print(f"venue={venue.value} config={args.config} regime={regime['state']} "
          f"breaker_scale={scale} as_of={regime['as_of']}")
    print("target weights:", {s: round(w, 4) for s, w in targets.items()})

    try:
        broker = make_broker(venue, prices=prices,
                             i_understand_live=args.i_understand_live)
        executor = Executor(broker=broker, risk=cfg.risk, breaker_scale=scale)
        preview = not args.execute
        record = executor.execute(targets, dry_preview=(preview and venue != Venue.DRY))
    except ExecutionError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 3

    if not record["orders"]:
        print("no orders: within rebalance band (nothing to do today)")
    else:
        for o in record["orders"]:
            print(f"  {o['status']:8} {o['side']:4} {o['symbol']:9} "
                  f"${o['notional']:>10,.2f}  (w {o['current_weight']:.3f}->{o['target_weight']:.3f})")
    mode = "PREVIEW (no orders sent)" if (not args.execute and venue != Venue.DRY) else \
           "DRY SIMULATION" if venue == Venue.DRY else "ORDERS SENT"
    print(f"mode: {mode}  | logged to out/execution_log.json")
    if venue != Venue.DRY and not args.execute:
        print("re-run with --execute to actually place these orders")

    # Reconciliation bridge: real (testnet/live) fills feed their observed
    # costs into the paper ledger, which is what the LIVE gate reads.
    if args.execute and venue != Venue.DRY:
        assumed_bps = cfg.costs.cost_per_side * 10_000
        recorded = 0
        for o in record["orders"]:
            if o.get("status") != "filled":
                continue
            bps = observed_cost_bps(o["symbol"], o.get("price"), o.get("fill"))
            if bps is None:
                continue
            account.record_external_fill(
                date=regime["as_of"], symbol=o["symbol"], side=o["side"],
                notional=o["notional"], fill_price=o.get("price"),
                observed_bps=bps, assumed_bps=assumed_bps,
                source=venue.value)
            recorded += 1
        if recorded:
            account.save()
            recon = account.reconciliation()
            print(f"reconciliation: +{recorded} observed fill(s); "
                  f"avg observed {recon.get('avg_observed_cost_bps_per_side', 0):.1f} bps "
                  f"vs assumed {assumed_bps:.0f} bps; "
                  f"within kill criterion: {recon.get('within_kill_criterion')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
