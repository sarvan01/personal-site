import pytest

from trading_system.config import DEFAULT
from trading_system.execution import (
    DryRunBroker,
    ExecutionError,
    Executor,
    Venue,
    make_broker,
)

PRICES = {"BTCUSDT": 50_000.0, "ETHUSDT": 2_500.0}


def broker(tmp_path, start_usdt=10_000.0):
    return DryRunBroker(PRICES, state_path=tmp_path / "dry.json", start_usdt=start_usdt)


def test_plan_buys_from_flat(tmp_path):
    ex = Executor(broker=broker(tmp_path), risk=DEFAULT.risk, log_path=tmp_path / "log.json")
    plans = ex.plan({"BTCUSDT": 0.10, "ETHUSDT": 0.05})
    sides = {p.symbol: p.side for p in plans}
    assert sides == {"BTCUSDT": "BUY", "ETHUSDT": "BUY"}
    btc = next(p for p in plans if p.symbol == "BTCUSDT")
    assert btc.notional == pytest.approx(0.10 * 10_000.0)


def test_rebalance_band_skips_dust(tmp_path):
    ex = Executor(broker=broker(tmp_path), risk=DEFAULT.risk, rebalance_band=0.01,
                  log_path=tmp_path / "log.json")
    # 0.05% of equity is below both the 1% band and the $10 min notional.
    plans = ex.plan({"BTCUSDT": 0.0005})
    assert plans == []


def test_pre_trade_rejects_oversized_weight(tmp_path):
    ex = Executor(broker=broker(tmp_path), risk=DEFAULT.risk, log_path=tmp_path / "log.json")
    with pytest.raises(ExecutionError, match="max_asset_weight"):
        ex.plan({"BTCUSDT": 0.50})  # exceeds 25% cap


def test_pre_trade_rejects_excess_gross(tmp_path):
    ex = Executor(broker=broker(tmp_path), risk=DEFAULT.risk, log_path=tmp_path / "log.json")
    with pytest.raises(ExecutionError, match="gross"):
        ex.plan({"BTCUSDT": 0.25, "ETHUSDT": 0.25, "BNBUSDT": 0.25,
                 "XRPUSDT": 0.25, "SOLUSDT": 0.25})  # sums to 125%


def test_breaker_flat_sells_to_cash(tmp_path):
    b = broker(tmp_path)
    b.state["BTC"] = 0.04  # hold 0.04 BTC = $2000 = 20% of equity
    ex = Executor(broker=b, risk=DEFAULT.risk, breaker_scale=0.0,
                  log_path=tmp_path / "log.json")
    plans = ex.plan({"BTCUSDT": 0.10})  # signal says long, but breaker is flat
    assert len(plans) == 1
    assert plans[0].side == "SELL"
    assert plans[0].reason == "breaker-flat"


def test_dry_execute_updates_balance_and_logs(tmp_path):
    b = broker(tmp_path)
    ex = Executor(broker=b, risk=DEFAULT.risk, log_path=tmp_path / "log.json")
    record = ex.execute({"BTCUSDT": 0.10})
    assert record["orders"][0]["status"] == "filled"
    assert b.state["BTC"] == pytest.approx(0.02)  # $1000 / $50k
    assert b.state["USDT"] == pytest.approx(9_000.0)
    assert (tmp_path / "log.json").exists()


def test_live_gate_blocks_without_env(tmp_path):
    with pytest.raises(ExecutionError, match="BINANCE_KEY"):
        make_broker(Venue.LIVE, env={})
    with pytest.raises(ExecutionError, match="ALLOW_LIVE_TRADING"):
        make_broker(Venue.LIVE, i_understand_live=True,
                    env={"BINANCE_KEY": "k", "BINANCE_SECRET": "s"})
    with pytest.raises(ExecutionError, match="i-understand-live"):
        make_broker(Venue.LIVE, i_understand_live=False,
                    env={"BINANCE_KEY": "k", "BINANCE_SECRET": "s",
                         "ALLOW_LIVE_TRADING": "yes"})


def test_dry_broker_needs_no_credentials():
    b = make_broker(Venue.DRY, prices=PRICES)
    assert b.name == "DRY"
    assert b.equity() > 0
