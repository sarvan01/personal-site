import numpy as np
import pandas as pd

from trading_system.indicators import (
    atr,
    donchian_high,
    donchian_low,
    drawdown,
    realized_vol,
    rolling_percentile_rank,
    sma,
)


def test_sma_matches_manual(btc):
    s = sma(btc["close"], 10)
    expected = btc["close"].iloc[0:10].mean()
    assert np.isclose(s.iloc[9], expected)
    assert s.iloc[:9].isna().all()


def test_donchian_channels_have_no_lookahead(btc):
    close = btc["close"]
    upper = donchian_high(close, 20)
    # The channel on day t must use only days t-20..t-1.
    t = 100
    assert np.isclose(upper.iloc[t], close.iloc[t - 20 : t].max())
    lower = donchian_low(close, 20)
    assert np.isclose(lower.iloc[t], close.iloc[t - 20 : t].min())


def test_realized_vol_positive_and_annualized(btc):
    vol = realized_vol(btc["close"], 30).dropna()
    assert (vol > 0).all()
    # Synthetic gen uses 2-5% daily vol -> annualized should be way above 10%.
    assert vol.median() > 0.10


def test_rolling_percentile_rank_bounds(btc):
    vol = realized_vol(btc["close"], 30)
    rank = rolling_percentile_rank(vol, 200).dropna()
    assert rank.between(0, 1).all()


def test_atr_positive(btc):
    a = atr(btc["high"], btc["low"], btc["close"], 20).dropna()
    assert (a > 0).all()


def test_drawdown_nonpositive_and_zero_at_peak():
    eq = pd.Series([100.0, 110.0, 99.0, 121.0])
    dd = drawdown(eq)
    assert dd.iloc[1] == 0.0
    assert np.isclose(dd.iloc[2], 99 / 110 - 1)
    assert (dd <= 0).all()
