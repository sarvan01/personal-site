"""Paper-trading engine (report section 8, weeks 3-4).

A persistent simulated account stepped forward one day at a time by the
daily signal run. Fills are simulated at the close with the configured
costs; the circuit-breaker state survives across runs in the ledger file.

Reconciliation: every fill records the cost assumption used, so when live
(testnet or real) fills exist later, observed costs can be compared against
these assumptions — the go/no-go gate before live capital.
"""

import json
from pathlib import Path

import pandas as pd

from .config import SystemConfig

LEDGER_PATH = Path(__file__).resolve().parent.parent / "out" / "paper_ledger.json"


def days_to_replay(last_date: str | None, index: pd.DatetimeIndex, default: int) -> int:
    """How many trailing bars of `index` the paper account must step through.

    Fresh ledger (last_date is None): return `default` (seed with N days of
    history). Otherwise: return the number of bars strictly after last_date
    through the latest bar, so a multi-day gap (e.g. the machine was off, or
    a daily run was skipped) is replayed in full rather than silently
    skipped — the naive "always step 1 day" approach would jump straight
    from the old date to the newest one, dropping every day's price move in
    between from the equity curve. Falls back to 1 if last_date can't be
    located in the index (e.g. the data was refetched with a different
    start date) — better to advance one day than raise on a rare edge case.
    """
    if last_date is None:
        return default
    ts = pd.Timestamp(last_date)
    if ts.tz is None and index.tz is not None:
        ts = ts.tz_localize(index.tz)
    if ts not in index:
        return 1
    pos = index.get_loc(ts)
    return max(len(index) - 1 - pos, 0)


class PaperAccount:
    def __init__(self, path: Path = LEDGER_PATH, start_equity: float = 100_000.0):
        self.path = path
        if path.exists():
            state = json.loads(path.read_text())
        else:
            state = {
                "equity": start_equity,
                "peak": start_equity,
                "cooldown_left": 0,
                "recovering": False,
                "weights": {},
                "history": [],
                "fills": [],
                "last_date": None,
            }
        self.state = state

    # -- circuit breaker (mirrors risk.CircuitBreaker, but persisted) -------
    def breaker_scale(self, cfg: SystemConfig) -> float:
        s = self.state
        s["peak"] = max(s["peak"], s["equity"])
        dd = s["equity"] / s["peak"] - 1.0 if s["peak"] > 0 else 0.0
        if s["cooldown_left"] > 0:
            s["cooldown_left"] -= 1
            return 0.0
        if dd <= -cfg.risk.dd_go_flat:
            s["cooldown_left"] = cfg.risk.breaker_cooldown_days
            s["recovering"] = True
            return 0.0
        if s["recovering"]:
            if s["equity"] >= s["peak"]:
                s["recovering"] = False
            else:
                return 0.5
        return 0.5 if dd <= -cfg.risk.dd_half_size else 1.0

    def step(
        self,
        date: str,
        closes: dict[str, float],
        prev_closes: dict[str, float],
        target_weights: dict[str, float],
        cfg: SystemConfig,
    ) -> dict:
        """Advance one day: earn yesterday's weights on today's returns, then
        rebalance to (breaker-scaled) targets at today's close."""
        s = self.state
        if s["last_date"] == date:
            return {"skipped": True, "reason": f"already stepped for {date}"}

        prev_w = s["weights"]
        day_ret = sum(
            w * (closes[sym] / prev_closes[sym] - 1.0)
            for sym, w in prev_w.items()
            if sym in closes and sym in prev_closes and prev_closes[sym] > 0
        )
        scale = self.breaker_scale(cfg)
        new_w = {sym: w * scale for sym, w in target_weights.items() if w * scale > 0}

        cost_rate = cfg.costs.cost_per_side
        turnover = sum(
            abs(new_w.get(sym, 0.0) - prev_w.get(sym, 0.0))
            for sym in set(new_w) | set(prev_w)
        )
        cost = turnover * cost_rate
        s["equity"] *= 1.0 + day_ret - cost

        for sym in sorted(set(new_w) | set(prev_w)):
            delta = new_w.get(sym, 0.0) - prev_w.get(sym, 0.0)
            if abs(delta) > 1e-9:
                s["fills"].append(
                    {
                        "date": date,
                        "symbol": sym,
                        "weight_change": round(delta, 6),
                        "fill_price": closes.get(sym),
                        "assumed_cost_bps_per_side": cost_rate * 10_000,
                        "observed_cost_bps_per_side": None,  # filled from testnet/live
                    }
                )
        s["weights"] = new_w
        s["history"].append({"date": date, "equity": round(s["equity"], 2)})
        s["last_date"] = date
        return {
            "date": date,
            "equity": s["equity"],
            "day_return": day_ret,
            "cost": cost,
            "breaker_scale": scale,
            "weights": new_w,
        }

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))
        return self.path

    def record_external_fill(self, date: str, symbol: str, side: str,
                             notional: float, fill_price: float | None,
                             observed_bps: float, assumed_bps: float,
                             source: str = "testnet") -> None:
        """Record a REAL (testnet/live) fill's observed cost so the
        reconciliation that gates LIVE can actually accumulate evidence --
        without this bridge, 'observed fills' stayed at 0 forever."""
        self.state["fills"].append({
            "date": date,
            "symbol": symbol,
            "side": side,
            "weight_change": 0.0,  # external fill: not part of paper P&L
            "notional": round(float(notional), 2),
            "fill_price": fill_price,
            "assumed_cost_bps_per_side": float(assumed_bps),
            "observed_cost_bps_per_side": round(float(observed_bps), 3),
            "source": source,
        })

    def reconciliation(self) -> dict:
        """Assumed vs. observed costs across fills (observed comes from
        testnet/live execution later; until then this reports coverage)."""
        fills = self.state["fills"]
        observed = [
            f["observed_cost_bps_per_side"]
            for f in fills
            if f["observed_cost_bps_per_side"] is not None
        ]
        out = {
            "n_fills": len(fills),
            "n_with_observed_costs": len(observed),
            "assumed_cost_bps_per_side": (
                fills[-1]["assumed_cost_bps_per_side"] if fills else None
            ),
        }
        if observed:
            avg = sum(observed) / len(observed)
            out["avg_observed_cost_bps_per_side"] = avg
            assumed = out["assumed_cost_bps_per_side"] or 1e-9
            out["observed_vs_assumed_ratio"] = avg / assumed
            # Kill criterion input (report section 5): live costs > 1.5x assumed.
            out["within_kill_criterion"] = avg <= 1.5 * assumed
        return out

    def summary(self) -> dict:
        s = self.state
        dd = s["equity"] / s["peak"] - 1.0 if s["peak"] > 0 else 0.0
        return {
            "equity": round(s["equity"], 2),
            "peak_equity": round(s["peak"], 2),
            "drawdown": round(dd, 4),
            "open_weights": s["weights"],
            "days_recorded": len(s["history"]),
            "breaker_cooldown_left": s["cooldown_left"],
        }
