"""Battle-test suite: each test documents an audit finding by FAILING until
the corresponding fix lands. Findings:

F1  Gross-cap divergence: backtest scales portfolio gross to max_gross;
    latest_targets (paper/display/executor input) never applied that cap, and
    the executor hard-rejected instead of scaling -- so on the system's
    highest-conviction days, backtest ~ 100% gross, paper held >100%, and
    live would have refused to trade at all.
F2  Daily replay crashed with KeyError if any symbol was missing a bar
    (exchange outage / later listing) inside the replay window.
F3  Live/testnet order sizing ignored Binance LOT_SIZE / NOTIONAL filters.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.config import DEFAULT, H1B, RiskConfig
from trading_system.data import synthetic_klines
from trading_system.execution import DryRunBroker, Executor
from trading_system.risk import cap_gross
from trading_system.signals import latest_targets


def _low_vol_uptrend(days=400, seed=1, start="2024-01-01"):
    """A calm, grinding uptrend: low ATR + low vol => per-asset weights near
    their caps for every symbol at once => raw gross well above 100%."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.004, 0.008, days)  # strong drift, tiny vol
    close = 1_000 * np.exp(np.cumsum(rets))
    close[-1] = close.max() * 1.02  # guarantee a breakout on the last bar
    idx = pd.date_range(start, periods=days, freq="D", tz="UTC")
    intraday = np.abs(rng.normal(0, 0.004, days))
    df = pd.DataFrame({
        "open": close, "high": close * (1 + intraday),
        "low": close * (1 - intraday), "close": close,
        "volume": np.full(days, 1e5),
    }, index=idx)
    df.index.name = "date"
    return df


def _hot_universe():
    return {s: _low_vol_uptrend(seed=i) for i, s in enumerate(H1B.universe)}


# ---------------------------------------------------------------------------
# F1 -- gross cap must bind everywhere, identically
# ---------------------------------------------------------------------------
def test_f1_cap_gross_scales_proportionally():
    targets = {"A": 0.30, "B": 0.30, "C": 0.30}  # gross 0.90 -> no change at 1.0
    capped, scale = cap_gross(targets, 1.0)
    assert scale == 1.0 and capped == targets
    capped, scale = cap_gross(targets, 0.45)  # gross 0.90 -> halve everything
    assert scale == pytest.approx(0.5)
    assert capped["A"] == pytest.approx(0.15)
    assert sum(capped.values()) == pytest.approx(0.45)


def test_f1_latest_targets_respects_max_gross():
    ohlc = _hot_universe()
    targets, regime = latest_targets(ohlc, H1B, lookback=50)
    gross = sum(v["target_weight"] for v in targets.values())
    # The raw per-asset weights in this calm uptrend exceed 100% combined;
    # after the fix the published targets must respect the portfolio cap.
    assert gross <= H1B.risk.max_gross + 1e-9, (
        f"latest_targets published {gross:.1%} gross -- above max_gross")
    assert regime["gross_scale"] <= 1.0  # cap factor is reported, not hidden


def test_f1_scenario_really_is_over_cap_before_scaling():
    # Guard against the test silently passing because the scenario got tame:
    # confirm the *uncapped* per-asset weights do sum above max_gross.
    ohlc = _hot_universe()
    targets, regime = latest_targets(ohlc, H1B, lookback=50)
    uncapped = sum(v["target_weight"] for v in targets.values()) / regime["gross_scale"]
    assert uncapped > H1B.risk.max_gross


def test_f1_executor_scales_instead_of_refusing():
    # Live path: an over-cap target set must be scaled to the cap and traded,
    # not rejected outright (rejection == flat on the best days).
    broker = DryRunBroker({"BTCUSDT": 100.0, "ETHUSDT": 100.0, "BNBUSDT": 100.0,
                           "XRPUSDT": 100.0, "SOLUSDT": 100.0},
                          state_path=Path("/tmp/f1_dry.json"), start_usdt=10_000.0)
    Path("/tmp/f1_dry.json").unlink(missing_ok=True)
    ex = Executor(broker=broker, risk=DEFAULT.risk, log_path=Path("/tmp/f1_log.json"))
    over = {s: 0.24 for s in H1B.universe}  # 120% gross, each under asset cap
    plans = ex.plan(over)  # must NOT raise
    total_target = sum(p.target_weight for p in plans)
    assert total_target <= DEFAULT.risk.max_gross + 1e-9
    # Proportional: every symbol still trades, scaled by the same factor.
    assert len(plans) == 5
    for p in plans:
        assert p.target_weight == pytest.approx(0.24 * (1.0 / 1.2), rel=1e-6)


def test_f1_executor_still_rejects_per_asset_violations():
    # The gross overflow is expected geometry; a single-asset cap violation is
    # an upstream bug and must still fail closed.
    broker = DryRunBroker({"BTCUSDT": 100.0}, state_path=Path("/tmp/f1b_dry.json"))
    Path("/tmp/f1b_dry.json").unlink(missing_ok=True)
    ex = Executor(broker=broker, risk=DEFAULT.risk, log_path=Path("/tmp/f1b_log.json"))
    from trading_system.execution import ExecutionError
    with pytest.raises(ExecutionError, match="max_asset_weight"):
        ex.plan({"BTCUSDT": 0.50})


# ---------------------------------------------------------------------------
# F2 -- a missing bar for one symbol must not crash the daily replay
# ---------------------------------------------------------------------------
def test_f2_replay_survives_missing_bar(tmp_path, monkeypatch):
    import trading_system.data as data_mod
    from trading_system.paper import PaperAccount

    monkeypatch.setattr(data_mod, "DATA_DIR", tmp_path)
    btc = synthetic_klines(days=200, seed=7)
    eth = synthetic_klines(days=200, seed=13)
    # Simulate an exchange outage: ETH is missing a bar inside the replay window.
    eth = eth.drop(eth.index[-10])
    data_mod.save_csv(btc, "BTCUSDT", "1d")
    data_mod.save_csv(eth, "ETHUSDT", "1d")

    from trading_system.signals import replay_targets

    ohlc = {"BTCUSDT": data_mod.load_klines("BTCUSDT"),
            "ETHUSDT": data_mod.load_klines("ETHUSDT")}
    account = PaperAccount(path=tmp_path / "ledger.json")
    # Must not raise KeyError; the missing day forward-fills.
    n = replay_targets(ohlc, DEFAULT, lookback=50, n_days=30,
                       account=account)
    assert n == 30
    assert account.state["last_date"] is not None
    assert len(account.state["history"]) == 30
