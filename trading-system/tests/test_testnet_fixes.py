"""Fixes from the first real testnet run:
  T1  equity() made one serial HTTP price request per held asset -- testnet
      pre-funds ~10 play assets and its API is slow, so the run looked hung.
      Now: ONE batch ticker request, cached per run.
  T2  Pre-funded junk assets the system never trades inflated equity,
      shrinking every target weight. Now: equity scoped to the managed
      universe + USDT.
  T3  Reconciliation bridge: real fills feed observed costs into the paper
      ledger; without it, the LIVE gate's 'observed fills' stayed 0 forever.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.config import DEFAULT
from trading_system.execution import (
    BinanceSpotBroker,
    DryRunBroker,
    Executor,
    Venue,
    observed_cost_bps,
)
from trading_system.paper import PaperAccount

ALL_TICKERS = [
    {"symbol": "BTCUSDT", "price": "50000"},
    {"symbol": "ETHUSDT", "price": "2000"},
    {"symbol": "LTCUSDT", "price": "100"},
    {"symbol": "TRXUSDT", "price": "0.1"},
]


def _resp(status=200, body=None):
    m = Mock()
    m.status_code = status
    m.json.return_value = body
    m.text = str(body)
    return m


def _broker():
    return BinanceSpotBroker(Venue.TESTNET, key="k", secret="s")


# -- T1: one batch request, not one per asset --------------------------------
def test_t1_prices_fetched_in_single_batch_request():
    b = _broker()
    with patch("trading_system.execution.requests") as mock_requests:
        mock_requests.get.return_value = _resp(body=ALL_TICKERS)
        assert b.price("BTCUSDT") == 50000.0
        assert b.price("ETHUSDT") == 2000.0
        assert b.price("LTCUSDT") == 100.0
        assert mock_requests.get.call_count == 1  # ONE call for all three


def test_t1_balances_cached_per_run():
    b = _broker()
    with patch.object(b, "_signed") as mock_signed:
        mock_signed.return_value = {"balances": [
            {"asset": "USDT", "free": "1000", "locked": "0"},
            {"asset": "BTC", "free": "0.1", "locked": "0"},
        ]}
        b._balances()
        b.holdings()
        b._balances()
        assert mock_signed.call_count == 1  # signed account call made once


# -- T2: equity scoped to the managed universe -------------------------------
def test_t2_equity_excludes_unmanaged_prefunded_assets():
    b = _broker()
    b._balances_cache = {"USDT": 1000.0, "BTC": 0.1, "LTC": 5.0, "TRX": 10000.0}
    b._price_cache = {t["symbol"]: float(t["price"]) for t in ALL_TICKERS}
    # Unscoped: junk counts (old behavior, still available).
    assert b.equity() == pytest.approx(1000 + 0.1 * 50000 + 5 * 100 + 10000 * 0.1)
    # Scoped to the universe the system manages: junk excluded.
    assert b.equity(relevant_bases={"BTC", "ETH"}) == pytest.approx(1000 + 5000)


def test_t2_plan_uses_scoped_equity(tmp_path):
    broker = Mock()
    broker.name = "TESTNET"
    broker.equity.return_value = 10_000.0
    broker.holdings.return_value = {}
    broker.price.return_value = 100.0
    ex = Executor(broker=broker, risk=DEFAULT.risk, log_path=tmp_path / "log.json")
    ex.plan({"BTCUSDT": 0.10, "ETHUSDT": 0.05})
    _, kwargs = broker.equity.call_args
    assert kwargs["relevant_bases"] == {"BTC", "ETH"}


# -- T3: observed-cost computation + reconciliation bridge --------------------
def test_t3_observed_cost_slippage_plus_usdt_commission():
    # Expected 100, filled at VWAP 100.2 (20 bps slippage), 0.1 USDT
    # commission on ~1002 notional (~1 bp) -> ~21 bps total.
    resp = {"fills": [
        {"price": "100.1", "qty": "5", "commission": "0.05", "commissionAsset": "USDT"},
        {"price": "100.3", "qty": "5", "commission": "0.05", "commissionAsset": "USDT"},
    ]}
    bps = observed_cost_bps("BTCUSDT", 100.0, resp)
    assert bps == pytest.approx(20 + 0.1 / (100.2 * 10) * 10_000, rel=1e-3)


def test_t3_observed_cost_base_asset_commission_converted():
    # SELL commission taken in base asset: 0.01 BTC at VWAP 100 = 1 USDT on
    # 1000 notional = 10 bps, plus zero slippage.
    resp = {"fills": [
        {"price": "100", "qty": "10", "commission": "0.01", "commissionAsset": "BTC"},
    ]}
    bps = observed_cost_bps("BTCUSDT", 100.0, resp)
    assert bps == pytest.approx(10.0, rel=1e-6)


def test_t3_observed_cost_none_for_dry_or_empty():
    assert observed_cost_bps("BTCUSDT", 100.0, {"simulated": True}) is None
    assert observed_cost_bps("BTCUSDT", 100.0, {}) is None
    assert observed_cost_bps("BTCUSDT", 0.0, {"fills": [{"price": "1", "qty": "1"}]}) is None


def test_t3_bridge_unlocks_reconciliation(tmp_path):
    acct = PaperAccount(path=tmp_path / "ledger.json")
    assert acct.reconciliation()["n_with_observed_costs"] == 0
    acct.record_external_fill(date="2026-07-27", symbol="BTCUSDT", side="SELL",
                              notional=1000.0, fill_price=100.0,
                              observed_bps=21.0, assumed_bps=25.0)
    acct.record_external_fill(date="2026-07-27", symbol="ETHUSDT", side="SELL",
                              notional=500.0, fill_price=2000.0,
                              observed_bps=15.0, assumed_bps=25.0)
    recon = acct.reconciliation()
    assert recon["n_with_observed_costs"] == 2
    assert recon["avg_observed_cost_bps_per_side"] == pytest.approx(18.0)
    assert recon["within_kill_criterion"] is True  # 18 <= 1.5 * 25


def test_t3_bridge_flags_kill_criterion_breach(tmp_path):
    acct = PaperAccount(path=tmp_path / "ledger.json")
    acct.record_external_fill(date="2026-07-27", symbol="BTCUSDT", side="BUY",
                              notional=1000.0, fill_price=100.0,
                              observed_bps=60.0, assumed_bps=25.0)
    recon = acct.reconciliation()
    assert recon["within_kill_criterion"] is False  # 60 > 37.5
