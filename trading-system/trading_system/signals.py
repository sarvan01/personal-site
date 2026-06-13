"""Shared signal -> target-weight computation.

Single source of truth used by the cockpit, the paper account, and the live
executor so all three agree on sizing. If this function says BTC = 8%, that
is what the dashboard shows, what the paper ledger books, and what the
executor would send to the venue.
"""

import pandas as pd

from .config import SystemConfig
from .indicators import realized_vol
from .regime import classify
from .risk import asset_weight
from .strategy import stop_distance, trend_signal


def latest_targets(
    ohlc: dict[str, pd.DataFrame],
    cfg: SystemConfig,
    lookback: int,
    macro_risk_off: pd.Series | None = None,
) -> tuple[dict, dict]:
    """Return (targets, regime) for the most recent bar.

    targets[symbol] = {signal, close, stop, vol, target_weight}
      target_weight is a fraction of account equity, already scaled by the
      regime exposure multiplier and clamped by the risk engine.
    regime = {state, multiplier, as_of}
    """
    bench = ohlc[cfg.benchmark]["close"]
    regime_df = classify(bench, cfg.regime, macro_risk_off=macro_risk_off)
    mult = float(regime_df["multiplier"].iloc[-1])

    targets = {}
    for sym, df in ohlc.items():
        sig = float(trend_signal(df["close"], lookback, cfg.trend.exit_divisor).iloc[-1])
        stop = float(stop_distance(df["high"], df["low"], df["close"], cfg.trend).iloc[-1])
        vol = float(realized_vol(df["close"], cfg.regime.vol_window).iloc[-1])
        price = float(df["close"].iloc[-1])
        weight = asset_weight(sig, vol, price, stop, cfg.risk) * mult
        targets[sym] = {
            "signal": bool(sig),
            "close": price,
            "stop": stop,
            "vol": vol,
            "target_weight": weight,
        }

    regime = {
        "state": regime_df["regime"].iloc[-1],
        "multiplier": mult,
        "as_of": str(regime_df.index[-1].date()),
    }
    return targets, regime
