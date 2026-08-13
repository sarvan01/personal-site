"""Sleeve A: long/flat Donchian trend-following on liquid majors.

Entry: close breaks above the prior `lookback`-day high.
Exit:  close breaks below the prior `lookback // exit_divisor`-day low.
No shorting. Signals are computed on closed bars and acted on the next bar
(the shift happens in the backtester, keeping this module lookahead-free
but immediately interpretable).
"""

import pandas as pd

from .config import TrendConfig
from .indicators import atr, donchian_high, donchian_low


def trend_signal(close: pd.Series, lookback: int, exit_divisor: int = 2) -> pd.Series:
    """Stateful long/flat (1/0) signal series."""
    upper = donchian_high(close, lookback)
    lower = donchian_low(close, max(lookback // exit_divisor, 2))
    raw = pd.Series(index=close.index, dtype=float)
    raw[close > upper] = 1.0
    raw[close < lower] = 0.0
    return raw.ffill().fillna(0.0)


def stop_distance(
    high: pd.Series, low: pd.Series, close: pd.Series, cfg: TrendConfig
) -> pd.Series:
    """ATR-based stop distance (price units) used for per-trade risk sizing."""
    return atr(high, low, close, cfg.atr_period) * cfg.atr_stop_mult


def signal_frame(
    ohlc: dict[str, pd.DataFrame], lookback: int, cfg: TrendConfig
) -> pd.DataFrame:
    """Signals for every symbol in the universe, aligned on a shared index."""
    signals = {
        sym: trend_signal(df["close"], lookback, cfg.exit_divisor)
        for sym, df in ohlc.items()
    }
    return pd.DataFrame(signals).fillna(0.0)
