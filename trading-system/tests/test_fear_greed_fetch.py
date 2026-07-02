import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "feeds"))

import fetch_fear_greed  # noqa: E402

from trading_system.milkroad import load_milkroad, write_milkroad  # noqa: E402

# Documented response shapes.
ALTERNATIVE_RESPONSE = {
    "name": "Fear and Greed Index",
    "data": [
        {"value": "19", "value_classification": "Extreme Fear",
         "timestamp": "1751500800", "time_until_update": "12345"}
    ],
    "metadata": {"error": None},
}
COINSTATS_RESPONSE = {
    "name": "Fear and Greed Index",
    "now": {"value": 73, "value_classification": "Greed",
            "timestamp": 1751500800, "update_time": "2026-07-02T13:00:00Z"},
    "yesterday": {"value": 70, "value_classification": "Greed"},
    "lastWeek": {"value": 55, "value_classification": "Neutral"},
}


def _mock_resp(status=200, body=None):
    m = Mock()
    m.status_code = status
    m.json.return_value = body
    m.text = str(body)
    return m


def test_label_for_bands():
    assert fetch_fear_greed.label_for(10) == "Extreme Fear"
    assert fetch_fear_greed.label_for(30) == "Fear"
    assert fetch_fear_greed.label_for(50) == "Neutral"
    assert fetch_fear_greed.label_for(60) == "Greed"
    assert fetch_fear_greed.label_for(90) == "Extreme Greed"


def test_fetch_alternative_parses_documented_shape():
    with patch.object(fetch_fear_greed, "requests") as mock_requests:
        mock_requests.get.return_value = _mock_resp(body=ALTERNATIVE_RESPONSE)
        value, label = fetch_fear_greed.fetch_alternative()
    assert value == 19
    assert label == "Extreme Fear"


def test_fetch_coinstats_parses_documented_shape(monkeypatch):
    monkeypatch.setenv("COINSTATS_API_KEY", "test-key")
    with patch.object(fetch_fear_greed, "requests") as mock_requests:
        mock_requests.get.return_value = _mock_resp(body=COINSTATS_RESPONSE)
        value, label = fetch_fear_greed.fetch_coinstats()
    assert value == 73
    assert label == "Greed"
    # Uses the X-API-KEY header, matching fetch_privacy.py's established pattern.
    _, kwargs = mock_requests.get.call_args
    assert kwargs["headers"]["X-API-KEY"] == "test-key"


def test_fetch_coinstats_requires_key(monkeypatch):
    monkeypatch.delenv("COINSTATS_API_KEY", raising=False)
    with pytest.raises(fetch_fear_greed.FetchError, match="COINSTATS_API_KEY"):
        fetch_fear_greed.fetch_coinstats()


def test_fetch_coinstats_http_error_raises(monkeypatch):
    monkeypatch.setenv("COINSTATS_API_KEY", "test-key")
    with patch.object(fetch_fear_greed, "requests") as mock_requests:
        mock_requests.get.return_value = _mock_resp(status=401, body={})
        with pytest.raises(fetch_fear_greed.FetchError, match="401"):
            fetch_fear_greed.fetch_coinstats()


def test_main_writes_to_milkroad_json(tmp_path, monkeypatch):
    # write_milkroad/load_milkroad are bound into fetch_fear_greed's namespace
    # at import time with MILKROAD_PATH as their default `path` argument, so
    # patching the trading_system.milkroad module attribute after the fact
    # does NOT redirect them (Python binds defaults at def-time). Redirect
    # the names actually used by fetch_fear_greed.main() instead, so the
    # test never touches the real project's data/milkroad.json.
    out_path = tmp_path / "milkroad.json"
    monkeypatch.setattr(fetch_fear_greed, "load_milkroad", lambda: load_milkroad(out_path))
    monkeypatch.setattr(fetch_fear_greed, "write_milkroad",
                        lambda data: write_milkroad(data, out_path))
    monkeypatch.setattr(fetch_fear_greed, "fetch_alternative", lambda: (19, "Extreme Fear"))
    monkeypatch.setattr(sys, "argv", ["fetch_fear_greed.py", "--source", "alternative"])

    rc = fetch_fear_greed.main()
    assert rc == 0
    data = load_milkroad(out_path)
    assert data["indicators"]["fear_greed"]["value"] == 19
    assert data["source"] == "alternative"
    assert not (Path(__file__).resolve().parent.parent / "data" / "milkroad.json").exists()


def test_main_reports_fetch_error_cleanly(monkeypatch, capsys):
    def _boom():
        raise fetch_fear_greed.FetchError("simulated failure")
    monkeypatch.setattr(fetch_fear_greed, "fetch_alternative", _boom)
    monkeypatch.setattr(sys, "argv", ["fetch_fear_greed.py", "--source", "alternative"])

    rc = fetch_fear_greed.main()
    assert rc == 2
    assert "simulated failure" in capsys.readouterr().err

