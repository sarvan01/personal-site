"""T4 -- Binance rejects signed requests whose timestamp is AHEAD of server
time (error -1021). The user's scheduled testnet run failed with exactly
this: local clock 1000ms ahead. recvWindow does NOT help (it only tolerates
late arrivals), so requests must be stamped in EXCHANGE time.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.execution import (
    RECV_WINDOW_MS,
    TIME_SAFETY_MS,
    BinanceSpotBroker,
    ExecutionError,
    Venue,
)

# The exact payload Binance returned in the user's failed run.
ERR_1021 = ('{"code":-1021,"msg":"Timestamp for this request was 1000ms '
            'ahead of the server\'s time."}')


def _resp(status=200, body=None, text=None):
    m = Mock()
    m.status_code = status
    m.json.return_value = body if body is not None else {}
    m.text = text if text is not None else str(body)
    return m


def _broker():
    return BinanceSpotBroker(Venue.TESTNET, key="k", secret="s")


def _stamp_of(mock_requests):
    """Extract the timestamp param from the last signed URL."""
    url = mock_requests.request.call_args[0][1]
    return int(url.split("timestamp=")[1].split("&")[0])


def test_offset_computed_from_server_time():
    b = _broker()
    with patch("trading_system.execution.requests") as mr, \
         patch("trading_system.execution.time") as mt:
        mt.time.return_value = 1_000.0                  # local = 1_000_000 ms
        mr.get.return_value = _resp(body={"serverTime": 1_000_000 - 1000})
        offset = b._sync_time()
    assert offset == -1000  # exchange is 1s BEHIND local (the user's case)


def test_signed_request_stamps_in_exchange_time():
    b = _broker()
    b._time_offset = -1000  # local clock 1s ahead of exchange
    with patch("trading_system.execution.requests") as mr, \
         patch("trading_system.execution.time") as mt:
        mt.time.return_value = 1_000.0                  # local = 1_000_000 ms
        mr.request.return_value = _resp(body={"ok": True})
        b._signed("GET", "/api/v3/account", {})
        stamp = _stamp_of(mr)
    # Corrected into exchange time, minus the safety margin -- so it can
    # never be ahead of the server.
    assert stamp == 1_000_000 - 1000 - TIME_SAFETY_MS


def test_recv_window_is_generous_for_latency():
    b = _broker()
    b._time_offset = 0
    with patch("trading_system.execution.requests") as mr:
        mr.request.return_value = _resp(body={})
        b._signed("GET", "/api/v3/account", {})
        url = mr.request.call_args[0][1]
    assert f"recvWindow={RECV_WINDOW_MS}" in url


def test_1021_triggers_resync_and_retry():
    """A stale offset mid-run must resync and retry once, not fail the day."""
    b = _broker()
    b._time_offset = 0
    calls = {"n": 0}

    def request(method, url, **kw):
        calls["n"] += 1
        return _resp(status=400, text=ERR_1021) if calls["n"] == 1 \
            else _resp(body={"ok": True})

    with patch("trading_system.execution.requests") as mr:
        mr.request.side_effect = request
        mr.get.return_value = _resp(body={"serverTime": 111_000})
        out = b._signed("GET", "/api/v3/account", {})
    assert out == {"ok": True}
    assert calls["n"] == 2          # failed once, retried once
    assert mr.get.called             # resynced in between


def test_retry_happens_only_once():
    """Persistent -1021 must surface as an error, not loop forever."""
    b = _broker()
    b._time_offset = 0
    with patch("trading_system.execution.requests") as mr:
        mr.request.return_value = _resp(status=400, text=ERR_1021)
        mr.get.return_value = _resp(body={"serverTime": 111_000})
        with pytest.raises(ExecutionError, match="-1021"):
            b._signed("GET", "/api/v3/account", {})
        assert mr.request.call_count == 2  # original + one retry, then stop


def test_retry_preserves_original_params():
    """The retry must resend the caller's params (minus the stale stamp),
    not a mangled set -- an order retry must still be the same order."""
    b = _broker()
    b._time_offset = 0
    seen = []

    def request(method, url, **kw):
        seen.append(url)
        return _resp(status=400, text=ERR_1021) if len(seen) == 1 \
            else _resp(body={"ok": True})

    with patch("trading_system.execution.requests") as mr:
        mr.request.side_effect = request
        mr.get.return_value = _resp(body={"serverTime": 111_000})
        b._signed("POST", "/api/v3/order",
                  {"symbol": "BTCUSDT", "side": "SELL", "type": "MARKET"})
    assert "symbol=BTCUSDT" in seen[1] and "side=SELL" in seen[1]
    assert seen[1].count("timestamp=") == 1  # exactly one fresh stamp


def test_unreachable_time_endpoint_degrades_to_local_clock(capsys):
    import requests as real_requests
    b = _broker()
    with patch("trading_system.execution.requests") as mr:
        mr.RequestException = real_requests.RequestException
        mr.get.side_effect = real_requests.RequestException("blocked")
        assert b._sync_time() == 0
    assert "could not sync" in capsys.readouterr().err


def test_large_drift_warns_the_user(capsys):
    b = _broker()
    with patch("trading_system.execution.requests") as mr, \
         patch("trading_system.execution.time") as mt:
        mt.time.return_value = 1_000.0
        mr.get.return_value = _resp(body={"serverTime": 1_000_000 + 30_000})
        b._sync_time()
    assert "w32tm /resync" in capsys.readouterr().out  # actionable hint
