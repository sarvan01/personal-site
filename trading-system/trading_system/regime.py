"""Market regime engine (report section 7).

Two measurable axes — trend and stress — collapse into four states, each
mapped to a gross-exposure multiplier. Built from the benchmark (BTC) series;
optional breadth input refines the trend axis when multiple symbols exist.
"""

from enum import Enum

import pandas as pd

from .config import RegimeConfig
from .indicators import pct_return, realized_vol, rolling_percentile_rank, sma


class Regime(str, Enum):
    RISK_ON_TRENDING = "risk_on_trending"
    RISK_ON_EUPHORIC = "risk_on_euphoric"
    CHOP = "chop"
    RISK_OFF = "risk_off"


def classify(
    benchmark_close: pd.Series,
    cfg: RegimeConfig,
    breadth: pd.Series | None = None,
) -> pd.DataFrame:
    """Return a DataFrame with columns: regime (str), multiplier (float).

    Trend axis: benchmark above its long SMA and positive trailing return
    (optionally confirmed by breadth > 0.5).
    Stress axis: 30-day realized vol in its top decile of the trailing year.
    """
    above_sma = benchmark_close > sma(benchmark_close, cfg.sma_long)
    pos_ret = pct_return(benchmark_close, cfg.return_lookback) > 0
    trend = above_sma & pos_ret
    if breadth is not None:
        trend = trend & (breadth >= 0.5)

    vol = realized_vol(benchmark_close, cfg.vol_window)
    vol_rank = rolling_percentile_rank(vol, cfg.vol_rank_window)
    stressed = vol_rank >= cfg.vol_extreme_pct

    regime = pd.Series(Regime.CHOP.value, index=benchmark_close.index)
    regime[trend & ~stressed] = Regime.RISK_ON_TRENDING.value
    regime[trend & stressed] = Regime.RISK_ON_EUPHORIC.value
    regime[~trend & stressed] = Regime.RISK_OFF.value

    multiplier = regime.map(
        {
            Regime.RISK_ON_TRENDING.value: cfg.mult_risk_on_trending,
            Regime.RISK_ON_EUPHORIC.value: cfg.mult_risk_on_euphoric,
            Regime.CHOP.value: cfg.mult_chop,
            Regime.RISK_OFF.value: cfg.mult_risk_off,
        }
    )
    # Warmup period (indicators undefined): be conservative, not flat.
    multiplier = multiplier.where(vol_rank.notna(), cfg.mult_chop)
    return pd.DataFrame({"regime": regime, "multiplier": multiplier})
