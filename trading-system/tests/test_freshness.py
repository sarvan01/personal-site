from datetime import datetime, timedelta, timezone

import pandas as pd

from trading_system.data import freshness_warnings


def _df_ending(days_ago: int) -> pd.DataFrame:
    end = datetime.now(timezone.utc).date() - timedelta(days=days_ago)
    idx = pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=5, freq="D")
    return pd.DataFrame({"close": range(5)}, index=idx)


def test_fresh_data_no_warning():
    # Newest completed bar is yesterday UTC (lag 1) — normal, no warning.
    ohlc = {"BTCUSDT": _df_ending(1), "ETHUSDT": _df_ending(1)}
    assert freshness_warnings(ohlc) == []


def test_today_bar_also_fine():
    # If today's bar is present (lag 0), still fine.
    ohlc = {"BTCUSDT": _df_ending(0)}
    assert freshness_warnings(ohlc) == []


def test_stale_data_warns_with_symbol_and_age():
    ohlc = {"BTCUSDT": _df_ending(1), "ETHUSDT": _df_ending(4)}
    warns = freshness_warnings(ohlc)
    assert len(warns) == 1
    assert "ETHUSDT" in warns[0]
    assert "STALE" in warns[0]


def test_empty_frame_warns():
    empty = pd.DataFrame({"close": []})
    warns = freshness_warnings({"BTCUSDT": empty})
    assert len(warns) == 1
    assert "no data rows" in warns[0]


def test_max_lag_days_is_configurable():
    ohlc = {"BTCUSDT": _df_ending(3)}
    assert freshness_warnings(ohlc, max_lag_days=1)  # 3 > 1 -> warns
    assert freshness_warnings(ohlc, max_lag_days=5) == []  # 3 <= 5 -> ok
