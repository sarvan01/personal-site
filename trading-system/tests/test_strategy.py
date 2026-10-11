import numpy as np
import pandas as pd

from trading_system.config import DEFAULT
from trading_system.regime import Regime, classify
from trading_system.strategy import signal_frame, stop_distance, trend_signal


def test_trend_signal_is_long_or_flat(btc):
    sig = trend_signal(btc["close"], 100)
    assert set(sig.unique()) <= {0.0, 1.0}


def test_trend_signal_goes_long_in_a_pure_uptrend():
    idx = pd.date_range("2022-01-01", periods=300, freq="D", tz="UTC")
    close = pd.Series(np.linspace(100, 400, 300), index=idx)
    sig = trend_signal(close, 50)
    assert sig.iloc[-1] == 1.0
    assert sig.iloc[60:].mean() > 0.9  # long essentially the whole time


def test_trend_signal_exits_in_a_crash():
    idx = pd.date_range("2022-01-01", periods=300, freq="D", tz="UTC")
    up = np.linspace(100, 300, 200)
    down = np.linspace(300, 120, 100)
    close = pd.Series(np.concatenate([up, down]), index=idx)
    sig = trend_signal(close, 50)
    assert sig.iloc[199] == 1.0  # long at the top
    assert sig.iloc[-1] == 0.0  # flat after the breakdown


def test_stop_distance_positive(btc):
    sd = stop_distance(btc["high"], btc["low"], btc["close"], DEFAULT.trend).dropna()
    assert (sd > 0).all()


def test_signal_frame_aligns_universe(btc, eth):
    frame = signal_frame({"BTCUSDT": btc, "ETHUSDT": eth}, 100, DEFAULT.trend)
    assert list(frame.columns) == ["BTCUSDT", "ETHUSDT"]
    assert len(frame) == len(btc)


def test_regime_states_and_multipliers(btc):
    out = classify(btc["close"], DEFAULT.regime)
    assert set(out["regime"].unique()) <= {r.value for r in Regime}
    assert out["multiplier"].between(0.25, 1.0).all()
    # The synthetic series has bull and bear segments: more than one state
    # should appear, otherwise the engine is inert.
    assert out["regime"].nunique() >= 2
