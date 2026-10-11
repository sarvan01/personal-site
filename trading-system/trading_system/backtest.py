"""Backtest harness (report section 5, validation protocol).

Daily bars. Signals computed on day t are executed at day t+1's close
(one-bar lag, no lookahead). Costs are charged on turnover at the
pessimistic per-side rate from CostConfig. The drawdown circuit breaker is
applied path-dependently, exactly as it would run live.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import SystemConfig
from .indicators import TRADING_DAYS, drawdown
from .regime import classify
from .risk import CircuitBreaker, target_weights
from .strategy import signal_frame, stop_distance


@dataclass
class BacktestResult:
    equity: pd.Series
    weights: pd.DataFrame
    metrics: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return self.metrics


def compute_metrics(equity: pd.Series, weights: pd.DataFrame) -> dict:
    rets = equity.pct_change().dropna()
    years = len(equity) / TRADING_DAYS
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    sharpe = (rets.mean() * TRADING_DAYS) / vol if vol > 0 else 0.0
    max_dd = drawdown(equity).min()
    exposure = weights.sum(axis=1).mean()
    turnover = weights.diff().abs().sum(axis=1).sum() / max(years, 1e-9)
    return {
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1),
        "cagr": float(cagr),
        "ann_vol": float(vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "avg_gross_exposure": float(exposure),
        "ann_turnover": float(turnover),
        "days": int(len(equity)),
    }


def run_backtest(
    ohlc: dict[str, pd.DataFrame],
    cfg: SystemConfig,
    lookback: int,
    start_equity: float = 100_000.0,
) -> BacktestResult:
    closes = pd.DataFrame({s: df["close"] for s, df in ohlc.items()}).dropna(how="all")
    closes = closes.ffill()
    signals = signal_frame(ohlc, lookback, cfg.trend).reindex(closes.index).fillna(0.0)
    stops = pd.DataFrame(
        {
            s: stop_distance(df["high"], df["low"], df["close"], cfg.trend)
            for s, df in ohlc.items()
        }
    ).reindex(closes.index)

    bench = closes[cfg.benchmark]
    breadth = None
    if len(closes.columns) > 1:
        above = closes > closes.rolling(100, min_periods=100).mean()
        breadth = above.mean(axis=1)
    regime = classify(bench, cfg.regime, breadth)

    weights = target_weights(
        signals, closes, stops, regime["multiplier"], cfg.risk
    )
    # One-bar execution lag: today's target trades at tomorrow's close.
    weights = weights.shift(1).fillna(0.0)

    # Explicit shift-divide instead of pct_change: identical math, avoids the
    # pandas 2.x fill_method FutureWarning on universes with later listings.
    rets = (closes / closes.shift(1) - 1.0).fillna(0.0)
    cost_per_side = cfg.costs.cost_per_side

    breaker = CircuitBreaker(cfg.risk)
    equity = pd.Series(index=closes.index, dtype=float)
    eq = start_equity
    prev_w = pd.Series(0.0, index=closes.columns)
    applied = weights.copy()

    for i, (day, w_target) in enumerate(weights.iterrows()):
        scale = breaker.step(eq)
        w = w_target * scale
        turnover = (w - prev_w).abs().sum()
        day_ret = float((prev_w * rets.loc[day]).sum()) - turnover * cost_per_side
        eq *= 1.0 + day_ret
        equity.iloc[i] = eq
        applied.loc[day] = w
        prev_w = w

    result = BacktestResult(equity=equity, weights=applied)
    result.metrics = compute_metrics(equity, applied)
    result.metrics["lookback"] = lookback
    return result


def run_grid(ohlc: dict[str, pd.DataFrame], cfg: SystemConfig) -> pd.DataFrame:
    """Run the full pre-declared lookback grid. Pass criterion (report 8):
    positive net return and Sharpe > 0.7 across the WHOLE grid."""
    rows = [run_backtest(ohlc, cfg, lb).metrics for lb in cfg.trend.lookbacks]
    return pd.DataFrame(rows).set_index("lookback")


def walk_forward(
    ohlc: dict[str, pd.DataFrame],
    cfg: SystemConfig,
    lookback: int,
    window_years: int = 2,
) -> pd.DataFrame:
    """Net performance in each rolling out-of-sample window.

    Windows are sliced by DATE on the benchmark calendar, not by row
    position: with mixed-history universes (SOL lists in 2020, BTC in 2017),
    positional slicing silently pulled later-era rows of short-history
    symbols into early windows, blending periods (audit finding F10). A
    symbol with no data inside a window is simply absent from that window.
    """
    bench_index = ohlc[cfg.benchmark].index
    window = window_years * TRADING_DAYS
    rows = []
    start = 0
    while start + window // 2 < len(bench_index):
        end = min(start + window, len(bench_index))
        d0, d1 = bench_index[start], bench_index[end - 1]
        chunk = {}
        for s, df in ohlc.items():
            sub = df.loc[d0:d1]
            if len(sub):
                chunk[s] = sub
        if end - start > lookback * 2 and cfg.benchmark in chunk:
            m = run_backtest(chunk, cfg, lookback).metrics
            rows.append(
                {
                    "from": str(d0.date()),
                    "to": str(d1.date()),
                    **{k: m[k] for k in ("total_return", "sharpe", "max_drawdown")},
                }
            )
        start += window
    return pd.DataFrame(rows)
