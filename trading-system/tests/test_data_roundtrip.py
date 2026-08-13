"""CSV round-trip regression tests.

The original bug: fetch_data.py saved tz-aware timestamps to CSV, but newer
pandas does not auto-parse them back via parse_dates=True, so loaders
returned a plain object Index and resample()/date() calls crashed. These
tests round-trip through real files to pin the fix.
"""

import pandas as pd

import trading_system.data as data
from trading_system.data import (
    load_funding,
    load_klines,
    save_csv,
    synthetic_funding,
    synthetic_klines,
)


def test_klines_roundtrip_preserves_datetime_index(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA_DIR", tmp_path)
    df = synthetic_klines(days=50, seed=1)
    save_csv(df, "TESTUSDT", "1d")
    loaded = load_klines("TESTUSDT")
    assert isinstance(loaded.index, pd.DatetimeIndex)
    assert str(loaded.index.tz) == "UTC"
    assert len(loaded) == len(df)
    # Downstream usage that crashed before the fix:
    assert loaded.index[0].date() is not None


def test_funding_roundtrip_supports_resample(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA_DIR", tmp_path)
    funding = synthetic_funding(days=20, seed=2)
    save_csv(funding, "TESTUSDT", "funding")
    loaded = load_funding("TESTUSDT")
    assert isinstance(loaded.index, pd.DatetimeIndex)
    # The exact call that raised TypeError on the un-parsed index:
    daily = loaded.resample("1D").sum()
    assert len(daily) == 20
