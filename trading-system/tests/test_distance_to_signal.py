"""Distance-to-signal: each asset shows the price that would flip it, so a
flat book is self-explanatory ('why isn't it trading?') rather than
ambiguous between 'no setup' and 'something is broken'.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.config import DEFAULT
from trading_system.cockpit import build_cockpit
from trading_system.signals import latest_targets


def _series(closes, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="D", tz="UTC")
    c = np.asarray(closes, dtype=float)
    df = pd.DataFrame({"open": c, "high": c * 1.005, "low": c * 0.995,
                       "close": c, "volume": np.full(len(c), 1e5)}, index=idx)
    df.index.name = "date"
    return df


def test_flat_asset_reports_entry_trigger_above_current_price():
    # Rally to 100 then drift down to 90: flat, needs a new 50d high to enter.
    closes = list(np.linspace(50, 100, 60)) + list(np.linspace(100, 90, 20))
    ohlc = {"BTCUSDT": _series(closes)}
    targets, _ = latest_targets(ohlc, DEFAULT, lookback=50)
    v = targets["BTCUSDT"]
    assert v["signal"] is False
    assert v["trigger_label"] == "entry above"
    # Trigger is the prior 50-day high (100), above the last close (90).
    assert v["trigger_price"] > v["close"]
    assert v["distance_pct"] == pytest.approx(v["trigger_price"] / v["close"] - 1)
    assert v["distance_pct"] > 0


def test_long_asset_reports_exit_trigger_below_current_price():
    # Steady uptrend ending at a new high: long, exit sits below.
    ohlc = {"BTCUSDT": _series(np.linspace(50, 150, 120))}
    targets, _ = latest_targets(ohlc, DEFAULT, lookback=50)
    v = targets["BTCUSDT"]
    assert v["signal"] is True
    assert v["trigger_label"] == "exit below"
    assert v["trigger_price"] < v["close"]
    assert v["distance_pct"] < 0


def test_insufficient_history_reports_no_trigger():
    ohlc = {"BTCUSDT": _series(np.linspace(50, 60, 20))}  # < 50d lookback
    targets, _ = latest_targets(ohlc, DEFAULT, lookback=50)
    v = targets["BTCUSDT"]
    assert v["trigger_price"] is None
    assert v["distance_pct"] is None


def test_cockpit_renders_trigger_and_explanatory_note(tmp_path):
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={"BTCUSDT": {"signal": False, "close": 90.0,
                             "target_weight": 0.0, "trigger_price": 100.0,
                             "trigger_label": "entry above",
                             "distance_pct": 0.1111}},
        carry={"signal": "OUT"}, risk={},
        data_mode="synthetic", out_dir=tmp_path,
    )
    html = path.read_text(encoding="utf-8")
    assert "entry above" in html
    assert "$100.00" in html
    assert "+11.1%" in html
    # The note that makes a flat book self-explanatory.
    assert "breakout system" in html and "8.5% gross exposure" in html


def test_cockpit_handles_missing_trigger_fields(tmp_path):
    # Older status.json / warming-up assets must not break rendering.
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={"BTCUSDT": {"signal": False, "close": 90.0, "target_weight": 0.0}},
        carry={"signal": "OUT"}, risk={},
        data_mode="synthetic", out_dir=tmp_path,
    )
    assert "warming up" in path.read_text(encoding="utf-8")


def test_main_thread_preserves_trigger_fields_into_signals(tmp_path, monkeypatch):
    """Regression test: main() used to narrow targets_full -> signals down to
    {signal, close, target_weight} before handing it to build_cockpit, silently
    dropping trigger_price/trigger_label/distance_pct on every real run (while
    unit tests on latest_targets()/build_cockpit() in isolation stayed green).
    That made every signal card show 'warming up' regardless of how much
    history was available.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import cockpit as cockpit_script
    from trading_system.paper import PaperAccount

    monkeypatch.setattr(
        cockpit_script, "PaperAccount",
        lambda: PaperAccount(path=tmp_path / "paper_ledger.json"))
    monkeypatch.setattr(sys, "argv", ["cockpit.py", "--synthetic", "--replay", "5"])

    rc = cockpit_script.main()
    assert rc == 0

    html = (cockpit_script.ROOT / "out" / "cockpit.html").read_text(encoding="utf-8")
    assert html.count("warming up") == 0
