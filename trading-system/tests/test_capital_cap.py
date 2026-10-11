"""--capital: live sizing is capped in code, not by how much sits in the account."""

import subprocess
import sys
from pathlib import Path

import pytest

from trading_system.config import DEFAULT
from trading_system.execution import DryRunBroker, ExecutionError, Executor

PRICES = {"BTCUSDT": 50_000.0, "ETHUSDT": 2_500.0}
ROOT = Path(__file__).resolve().parent.parent


def _executor(tmp_path, cap, start_usdt=100_000.0):
    b = DryRunBroker(PRICES, state_path=tmp_path / "dry.json", start_usdt=start_usdt)
    return Executor(broker=b, risk=DEFAULT.risk, capital_cap=cap,
                    log_path=tmp_path / "log.json")


def test_cap_sizes_against_cap_not_full_account(tmp_path):
    plans = _executor(tmp_path, cap=10_000.0).plan({"BTCUSDT": 0.10})
    assert plans[0].notional == pytest.approx(1_000.0)  # 10% of 10k, not of 100k


def test_cap_above_account_equity_has_no_effect(tmp_path):
    plans = _executor(tmp_path, cap=1e9, start_usdt=10_000.0).plan({"BTCUSDT": 0.10})
    assert plans[0].notional == pytest.approx(1_000.0)


def test_existing_position_counts_against_cap(tmp_path):
    ex = _executor(tmp_path, cap=10_000.0)
    ex.execute({"BTCUSDT": 0.10})            # buys $1,000 of BTC
    assert ex.plan({"BTCUSDT": 0.10}) == []  # already at target: no re-buy
    plans = ex.plan({"BTCUSDT": 0.20})
    assert plans[0].side == "BUY"
    assert plans[0].notional == pytest.approx(1_000.0)


def test_non_positive_cap_rejected(tmp_path):
    with pytest.raises(ExecutionError):
        _executor(tmp_path, cap=0.0).plan({"BTCUSDT": 0.10})


def test_live_without_capital_is_blocked_before_anything_else():
    env = {"ALLOW_LIVE_TRADING": "yes", "BINANCE_KEY": "x", "BINANCE_SECRET": "y",
           "PATH": "", "SYSTEMROOT": ""}
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "execute.py"),
         "--venue", "live", "--i-understand-live"],
        capture_output=True, text=True, env=env, cwd=ROOT)
    assert r.returncode == 3
    assert "--capital" in r.stderr
