"""Sleeve B: delta-neutral funding-rate carry (report section 5).

Long spot, short the same notional in the perp; collect funding while the
trailing 7-day average annualized rate exceeds the entry hurdle, exit when
it decays below the exit hurdle (hysteresis avoids churn). This module
monitors and backtests the carry; it never places orders.
"""

import pandas as pd

from .config import CarryConfig, CostConfig


def annualized_funding(funding_8h: pd.Series, cfg: CarryConfig) -> pd.Series:
    """Trailing N-day average funding, annualized, indexed daily."""
    daily = funding_8h.resample("1D").sum()  # 3 periods/day summed
    return (daily.rolling(cfg.avg_window_days, min_periods=cfg.avg_window_days).mean()) * 365


def carry_signal(funding_8h: pd.Series, cfg: CarryConfig) -> pd.Series:
    """Stateful in/out (1/0) daily signal with hysteresis hurdles."""
    ann = annualized_funding(funding_8h, cfg)
    raw = pd.Series(index=ann.index, dtype=float)
    raw[ann > cfg.enter_hurdle_annual] = 1.0
    raw[ann < cfg.exit_hurdle_annual] = 0.0
    return raw.ffill().fillna(0.0)


def backtest_carry(
    funding_8h: pd.Series, cfg: CarryConfig, costs: CostConfig
) -> dict:
    """Net annualized return of the carry sleeve per unit of sleeve capital.

    P&L = funding collected while in (short perp receives positive funding).
    Costs: four sides per round trip (enter+exit on both spot and perp legs).
    Basis convergence P&L is ignored (conservative for entries at positive
    basis, which is when the signal fires).
    """
    signal = carry_signal(funding_8h, cfg)
    daily_funding = funding_8h.resample("1D").sum()
    # Funding accrues while holding: lag the signal one day (no lookahead).
    held = signal.shift(1).fillna(0.0)
    gross = (held * daily_funding).fillna(0.0)
    round_trips = signal.diff().abs().fillna(0.0).sum() / 2
    total_costs = round_trips * 4 * costs.cost_per_side
    years = max(len(daily_funding) / 365, 1e-9)
    net_total = gross.sum() - total_costs
    return {
        "ann_net_return_on_sleeve": float(net_total / years),
        "time_in_market": float(held.mean()),
        "round_trips": float(round_trips),
        "ann_gross_return_on_sleeve": float(gross.sum() / years),
    }


def current_status(funding_8h: pd.Series, cfg: CarryConfig) -> dict:
    ann = annualized_funding(funding_8h, cfg)
    latest = float(ann.dropna().iloc[-1]) if not ann.dropna().empty else 0.0
    in_market = bool(carry_signal(funding_8h, cfg).iloc[-1])
    return {
        "trailing_7d_funding_annualized": latest,
        "signal": "IN" if in_market else "OUT",
        "enter_hurdle": cfg.enter_hurdle_annual,
        "exit_hurdle": cfg.exit_hurdle_annual,
        "max_sleeve_weight": cfg.max_sleeve_weight,
    }
