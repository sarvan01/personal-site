"""Small, dependency-light indicator helpers used by the strategy, regime
engine, and risk engine. All functions take/return pandas Series aligned to
the input index and only ever look backward (no lookahead).
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 365  # crypto trades every day


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def pct_return(close: pd.Series, window: int) -> pd.Series:
    return close.pct_change(window)


def realized_vol(close: pd.Series, window: int) -> pd.Series:
    """Annualized realized volatility of daily log returns."""
    logret = np.log(close / close.shift(1))
    return logret.rolling(window, min_periods=window).std() * np.sqrt(TRADING_DAYS)


def rolling_percentile_rank(series: pd.Series, window: int) -> pd.Series:
    """Percentile rank of the latest value within its trailing window."""

    def _rank(x: np.ndarray) -> float:
        return float((x[:-1] <= x[-1]).mean()) if len(x) > 1 else np.nan

    return series.rolling(window, min_periods=window // 2).apply(_rank, raw=True)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def donchian_high(close: pd.Series, window: int) -> pd.Series:
    """Highest close of the *previous* `window` days (shifted: no lookahead)."""
    return close.rolling(window, min_periods=window).max().shift(1)


def donchian_low(close: pd.Series, window: int) -> pd.Series:
    """Lowest close of the *previous* `window` days (shifted: no lookahead)."""
    return close.rolling(window, min_periods=window).min().shift(1)


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0
