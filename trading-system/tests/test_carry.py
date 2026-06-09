import numpy as np
import pandas as pd

from trading_system.carry import (
    annualized_funding,
    backtest_carry,
    carry_signal,
    current_status,
)
from trading_system.config import DEFAULT


def _constant_funding(rate_8h: float, days: int = 60) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=days * 3, freq="8h", tz="UTC")
    return pd.Series(rate_8h, index=idx)


def test_annualization_of_constant_funding():
    # 0.01% per 8h = 0.03%/day -> ~10.95% annualized.
    ann = annualized_funding(_constant_funding(0.0001), DEFAULT.carry).dropna()
    assert np.allclose(ann, 0.0001 * 3 * 365)


def test_signal_enters_above_hurdle_and_exits_below():
    hot = _constant_funding(0.0002)  # ~21.9% annualized > 10% hurdle
    assert carry_signal(hot, DEFAULT.carry).iloc[-1] == 1.0
    cold = _constant_funding(0.00003)  # ~3.3% annualized < 5% exit hurdle
    assert carry_signal(cold, DEFAULT.carry).iloc[-1] == 0.0


def test_hysteresis_holds_between_hurdles():
    # Hot stretch then mid-band: signal should stay IN (between 5% and 10%).
    hot = _constant_funding(0.0002, days=30)
    mid_idx = pd.date_range(
        hot.index[-1] + pd.Timedelta(hours=8), periods=90, freq="8h", tz="UTC"
    )
    mid = pd.Series(0.00007, index=mid_idx)  # ~7.7% annualized
    sig = carry_signal(pd.concat([hot, mid]), DEFAULT.carry)
    assert sig.iloc[-1] == 1.0


def test_backtest_carry_collects_funding_net_of_costs(funding):
    out = backtest_carry(funding, DEFAULT.carry, DEFAULT.costs)
    assert out["ann_gross_return_on_sleeve"] >= out["ann_net_return_on_sleeve"]
    assert 0.0 <= out["time_in_market"] <= 1.0


def test_current_status_shape(funding):
    status = current_status(funding, DEFAULT.carry)
    assert status["signal"] in ("IN", "OUT")
    assert status["max_sleeve_weight"] == DEFAULT.carry.max_sleeve_weight
