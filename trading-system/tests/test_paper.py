from pathlib import Path

import numpy as np

from trading_system.config import DEFAULT
from trading_system.paper import PaperAccount


def make_account(tmp_path: Path) -> PaperAccount:
    return PaperAccount(path=tmp_path / "ledger.json", start_equity=100_000.0)


def test_step_applies_returns_and_costs(tmp_path):
    acct = make_account(tmp_path)
    # Day 1: open a 10% BTC position (no prior weights -> no return, only cost).
    out1 = acct.step("2026-01-01", {"BTC": 100.0}, {"BTC": 100.0}, {"BTC": 0.10}, DEFAULT)
    cost = 0.10 * DEFAULT.costs.cost_per_side
    assert np.isclose(out1["equity"], 100_000.0 * (1 - cost))
    # Day 2: BTC +2% on a 10% weight, same target -> +0.2%, no turnover.
    out2 = acct.step("2026-01-02", {"BTC": 102.0}, {"BTC": 100.0}, {"BTC": 0.10}, DEFAULT)
    assert np.isclose(out2["day_return"], 0.002)
    assert out2["cost"] == 0.0


def test_same_day_step_is_idempotent(tmp_path):
    acct = make_account(tmp_path)
    acct.step("2026-01-01", {"BTC": 100.0}, {"BTC": 100.0}, {"BTC": 0.10}, DEFAULT)
    eq = acct.state["equity"]
    again = acct.step("2026-01-01", {"BTC": 100.0}, {"BTC": 100.0}, {"BTC": 0.10}, DEFAULT)
    assert again.get("skipped") is True
    assert acct.state["equity"] == eq


def test_breaker_flattens_after_15pct_drawdown(tmp_path):
    acct = make_account(tmp_path)
    acct.step("d0", {"BTC": 100.0}, {"BTC": 100.0}, {"BTC": 0.25}, DEFAULT)
    # Force equity down 16% and step: breaker must zero the new weights.
    acct.state["equity"] = acct.state["peak"] * 0.84
    out = acct.step("d1", {"BTC": 100.0}, {"BTC": 100.0}, {"BTC": 0.25}, DEFAULT)
    assert out["breaker_scale"] == 0.0
    assert out["weights"] == {}
    assert acct.state["cooldown_left"] == DEFAULT.risk.breaker_cooldown_days


def test_ledger_persists_and_reloads(tmp_path):
    acct = make_account(tmp_path)
    acct.step("2026-01-01", {"BTC": 100.0}, {"BTC": 100.0}, {"BTC": 0.10}, DEFAULT)
    acct.save()
    reloaded = PaperAccount(path=tmp_path / "ledger.json")
    assert reloaded.state["last_date"] == "2026-01-01"
    assert len(reloaded.state["fills"]) == 1
    recon = reloaded.reconciliation()
    assert recon["n_fills"] == 1
    assert recon["n_with_observed_costs"] == 0
