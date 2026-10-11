"""After go-live, the cost kill criterion judges live fills alone -- cheap
testnet fills must not dilute expensive real-money execution."""

from trading_system.paper import PaperAccount


def _account(tmp_path, testnet_bps, live_bps):
    acct = PaperAccount(path=tmp_path / "ledger.json")
    for i, bps in enumerate(testnet_bps):
        acct.record_external_fill(f"2026-09-{i + 1:02d}", "BTCUSDT", "BUY", 100.0,
                                  50_000.0, bps, 25.0, source="testnet")
    for i, bps in enumerate(live_bps):
        acct.record_external_fill(f"2026-10-{i + 1:02d}", "BTCUSDT", "BUY", 100.0,
                                  50_000.0, bps, 25.0, source="live")
    return acct.reconciliation()


def test_expensive_live_fills_trip_kill_despite_cheap_testnet_history(tmp_path):
    r = _account(tmp_path, [1.1] * 41, [60.0] * 5)
    # Blended average (~7.5 bps) would pass; live alone (60 bps) must not.
    assert r["avg_observed_cost_bps_per_side"] < 37.5
    assert r["n_live_observed"] == 5
    assert r["within_kill_criterion"] is False


def test_cheap_live_fills_pass(tmp_path):
    r = _account(tmp_path, [1.1] * 41, [12.0] * 3)
    assert r["within_kill_criterion"] is True
    assert r["avg_live_cost_bps_per_side"] == 12.0


def test_testnet_only_behaves_as_before(tmp_path):
    r = _account(tmp_path, [1.1] * 41, [])
    assert r["n_live_observed"] == 0
    assert r["within_kill_criterion"] is True
    assert "avg_live_cost_bps_per_side" not in r
