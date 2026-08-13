"""F3 -- live/testnet order sizing must respect Binance exchange filters."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.execution import (
    BinanceSpotBroker,
    ExecutionError,
    Executor,
    Venue,
)

XRP_EXCHANGE_INFO = {
    "symbols": [{
        "symbol": "XRPUSDT",
        "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "1.00000000",
             "minQty": "1.00000000", "maxQty": "9000000"},
            {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
        ],
    }]
}


def _broker():
    return BinanceSpotBroker(Venue.TESTNET, key="k", secret="s")


def _resp(status=200, body=None):
    m = Mock()
    m.status_code = status
    m.json.return_value = body or {}
    m.text = str(body)
    return m


def test_quantize_floors_to_step():
    q = BinanceSpotBroker._quantize
    assert q(123.7, 1.0) == 123.0          # XRP-style whole units
    assert q(0.123456789, 0.00001) == pytest.approx(0.12345)
    assert q(5.0, 1.0) == 5.0              # exact multiple not knocked down
    assert q(0.25, 0.1) == pytest.approx(0.2)  # clearly below -> floors
    # 0.3/0.1 is 2.999...96 in floats; must NOT get knocked down to 0.2.
    assert q(0.3, 0.1) == pytest.approx(0.3)
    assert q(1.23456789, 0.0) == pytest.approx(1.23456789)  # no filter info


def test_sell_uses_quantized_qty(monkeypatch):
    b = _broker()
    monkeypatch.setattr(b, "_filters", lambda s: {"step_size": 1.0, "min_qty": 1.0,
                                                  "min_notional": 5.0})
    monkeypatch.setattr(b, "price", lambda s: 2.0)  # $2/XRP
    captured = {}
    monkeypatch.setattr(b, "_signed", lambda m, p, params: captured.update(params) or {})
    b.market_order("XRPUSDT", "SELL", notional=100.0)  # 50 XRP exactly
    assert captured["quantity"] == "50"
    b.market_order("XRPUSDT", "SELL", notional=101.5)  # 50.75 -> floors to 50
    assert captured["quantity"] == "50"


def test_below_min_notional_raises_skippable_error(monkeypatch):
    b = _broker()
    monkeypatch.setattr(b, "_filters", lambda s: {"step_size": 1.0, "min_qty": 1.0,
                                                  "min_notional": 5.0})
    with pytest.raises(ExecutionError, match="below exchange minimum"):
        b.market_order("XRPUSDT", "BUY", notional=3.0)


def test_below_min_qty_raises_skippable_error(monkeypatch):
    b = _broker()
    monkeypatch.setattr(b, "_filters", lambda s: {"step_size": 1.0, "min_qty": 1.0,
                                                  "min_notional": 0.0})
    monkeypatch.setattr(b, "price", lambda s: 100.0)
    with pytest.raises(ExecutionError, match="quantized qty"):
        b.market_order("XRPUSDT", "SELL", notional=50.0)  # 0.5 -> floors to 0


def test_filters_parsed_from_exchange_info(monkeypatch):
    b = _broker()
    with patch("trading_system.execution.requests") as mock_requests:
        mock_requests.get.return_value = _resp(body=XRP_EXCHANGE_INFO)
        f = b._filters("XRPUSDT")
    assert f == {"step_size": 1.0, "min_qty": 1.0, "min_notional": 5.0}
    # Cached: a second call must not hit the network again.
    with patch("trading_system.execution.requests") as mock_requests:
        f2 = b._filters("XRPUSDT")
        mock_requests.get.assert_not_called()
    assert f2 == f


def test_filters_degrade_gracefully_when_unreachable(monkeypatch, capsys):
    import requests as real_requests
    b = _broker()
    with patch("trading_system.execution.requests") as mock_requests:
        mock_requests.RequestException = real_requests.RequestException
        mock_requests.get.side_effect = real_requests.RequestException("blocked")
        f = b._filters("BTCUSDT")
    assert f == {"step_size": 0.0, "min_qty": 0.0, "min_notional": 0.0}
    assert "warning" in capsys.readouterr().out


def test_execute_continues_past_skipped_order(tmp_path):
    """A min-notional skip on one symbol must not abort the others."""
    broker = Mock()
    broker.name = "TESTNET"
    broker.equity.return_value = 10_000.0
    broker.holdings.return_value = {}
    broker.price.return_value = 100.0
    calls = []

    def order(symbol, side, notional):
        if symbol == "XRPUSDT":
            raise ExecutionError("below exchange minimum")
        calls.append(symbol)
        return {"ok": True}

    broker.market_order.side_effect = order
    ex = Executor(broker=broker, risk=__import__("trading_system.config",
                                                 fromlist=["DEFAULT"]).DEFAULT.risk,
                  log_path=tmp_path / "log.json")
    record = ex.execute({"BTCUSDT": 0.10, "XRPUSDT": 0.10, "ETHUSDT": 0.10})
    statuses = {o["symbol"]: o["status"] for o in record["orders"]}
    assert statuses["XRPUSDT"] == "skipped"
    assert statuses["BTCUSDT"] == "filled"
    assert statuses["ETHUSDT"] == "filled"
    assert set(calls) == {"BTCUSDT", "ETHUSDT"}
