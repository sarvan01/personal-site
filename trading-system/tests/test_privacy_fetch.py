import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fetch_privacy import points_to_frame, prices_to_frame  # noqa: E402

from trading_system.data import _utc_index
from trading_system.event_study import run_event_study, synthetic_study_data


def test_coingecko_ms_normalizes_and_dedups():
    # Two ticks on the same UTC day -> one row (last wins). CoinGecko: ms.
    day = pd.Timestamp("2022-08-08", tz="UTC")
    ms = int(day.timestamp() * 1000)
    prices = [[ms, 100.0], [ms + 3_600_000, 110.0], [ms + 86_400_000, 120.0]]
    df = prices_to_frame(prices)
    assert list(df.columns) == ["close"]
    assert len(df) == 2  # two distinct days
    assert df["close"].iloc[0] == 110.0  # last tick of day 1 kept
    assert df.index.tz is not None


def test_coinstats_seconds_are_detected():
    # CoinStats returns unix SECONDS and may carry extra fields per point.
    day = pd.Timestamp("2024-02-06", tz="UTC")
    sec = int(day.timestamp())
    points = [[sec, 150.0, 1234, 0.004], [sec + 86_400, 160.0, 5678, 0.005]]
    df = points_to_frame(points)
    assert len(df) == 2
    assert df.index[0] == day  # parsed as seconds, not 1970
    assert df["close"].iloc[1] == 160.0


def test_csv_roundtrip_feeds_event_study(tmp_path):
    """The real cockpit path: write PRIV_*_1d.csv, read them back with the
    same loader cockpit uses, and run the event study end to end."""
    basket, bench, events = synthetic_study_data(effect=0.06, seed=4)
    cols = {}
    for sym in basket.columns:
        path = tmp_path / f"PRIV_{sym}_1d.csv"
        basket[[sym]].rename(columns={sym: "close"}).to_csv(path, index_label="date")
        loaded = pd.read_csv(path, index_col=0)
        loaded.index = _utc_index(loaded.index)
        cols[sym] = loaded["close"]
    reread = pd.DataFrame(cols)

    result = run_event_study(reread, bench, events, n_perm=300, seed=1)
    assert "[0,5]" in result.windows
    assert result.windows["[0,5]"]["n_events"] > 0
    assert isinstance(result.verdict, str)
