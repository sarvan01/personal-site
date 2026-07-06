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
from .risk import asset_weight, cap_gross
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

    # Portfolio gross cap -- the same layer-2 scaling the backtest applies,
    # so what the dashboard shows and the executor sends can never exceed
    # max_gross even when every asset hits its per-asset cap at once.
    raw = {s: v["target_weight"] for s, v in targets.items()}
    capped, gross_scale = cap_gross(raw, cfg.risk.max_gross)
    for sym in targets:
        targets[sym]["target_weight"] = capped[sym]

    regime = {
        "state": regime_df["regime"].iloc[-1],
        "multiplier": mult,
        "gross_scale": gross_scale,
        "as_of": str(regime_df.index[-1].date()),
    }
    return targets, regime


def replay_targets(
    ohlc: dict[str, pd.DataFrame],
    cfg: SystemConfig,
    lookback: int,
    n_days: int,
    account,
) -> int:
    """Step the paper account through the last `n_days` bars, computing each
    day's targets with that day's own signal/vol/stop values -- identical
    math to a live daily run, replayed. Returns the number of days stepped.

    Hardened against ragged data: every series is aligned to the benchmark
    calendar and forward-filled, so a symbol missing a bar (exchange outage)
    or listed later than the window start contributes its last known price
    (or is skipped entirely while it has no data) instead of crashing the
    daily run with a KeyError.
    """
    bench_index = ohlc[cfg.benchmark].index
    regime_df = classify(ohlc[cfg.benchmark]["close"], cfg.regime)

    aligned_close, sig_series, stop_series, vol_series = {}, {}, {}, {}
    for sym, df in ohlc.items():
        aligned_close[sym] = df["close"].reindex(bench_index).ffill()
        sig_series[sym] = (
            trend_signal(df["close"], lookback, cfg.trend.exit_divisor)
            .reindex(bench_index).ffill().fillna(0.0)
        )
        stop_series[sym] = (
            stop_distance(df["high"], df["low"], df["close"], cfg.trend)
            .reindex(bench_index).ffill()
        )
        vol_series[sym] = (
            realized_vol(df["close"], cfg.regime.vol_window)
            .reindex(bench_index).ffill()
        )

    stepped = 0
    for i in range(-n_days, 0):
        day = bench_index[i]
        pos = bench_index.get_loc(day)
        closes, prev_closes, targets = {}, {}, {}
        mult = float(regime_df["multiplier"].loc[day])
        for sym in ohlc:
            close = aligned_close[sym].iloc[pos]
            prev = aligned_close[sym].iloc[pos - 1] if pos > 0 else close
            if pd.isna(close) or pd.isna(prev):
                continue  # symbol has no data yet at this date: skip it
            closes[sym] = float(close)
            prev_closes[sym] = float(prev)
            stop = stop_series[sym].iloc[pos]
            vol = vol_series[sym].iloc[pos]
            sig = float(sig_series[sym].iloc[pos])
            if pd.isna(stop) or pd.isna(vol):
                targets[sym] = 0.0
                continue
            targets[sym] = asset_weight(sig, float(vol), closes[sym],
                                        float(stop), cfg.risk) * mult
        targets, _ = cap_gross(targets, cfg.risk.max_gross)
        account.step(str(day.date()), closes, prev_closes, targets, cfg)
        stepped += 1
    return stepped
