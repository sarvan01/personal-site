import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "feeds"))

import fetch_fear_greed  # noqa: E402

from trading_system.milkroad import load_milkroad, write_milkroad  # noqa: E402

# The documented alternative.me response shape (stable since ~2018).
SAMPLE_RESPONSE = {
    "name": "Fear and Greed Index",
    "data": [
        {"value": "19", "value_classification": "Extreme Fear",
         "timestamp": "1751500800", "time_until_update": "12345"}
    ],
    "metadata": {"error": None},
}


def _mock_resp(status=200, body=None):
    m = Mock()
    m.status_code = status
    m.json.return_value = body if body is not None else SAMPLE_RESPONSE
    m.text = str(body)
    return m


def test_label_for_bands():
    assert fetch_fear_greed.label_for(10) == "Extreme Fear"
    assert fetch_fear_greed.label_for(30) == "Fear"
    assert fetch_fear_greed.label_for(50) == "Neutral"
    assert fetch_fear_greed.label_for(60) == "Greed"
    assert fetch_fear_greed.label_for(90) == "Extreme Greed"


def test_main_parses_documented_shape_and_writes(tmp_path, monkeypatch):
    # write_milkroad/load_milkroad are bound into fetch_fear_greed's namespace
    # at import time with MILKROAD_PATH as their default `path` argument, so
    # patching the trading_system.milkroad module attribute after the fact
    # does NOT redirect them (Python binds defaults at def-time). Redirect
    # the names actually used by fetch_fear_greed.main() instead, so the
    # test never touches the real project's data/milkroad.json.
    out_path = tmp_path / "milkroad.json"
    monkeypatch.setattr(fetch_fear_greed, "requests",
                        Mock(get=Mock(return_value=_mock_resp())))
    monkeypatch.setattr(fetch_fear_greed, "load_milkroad",
                        lambda: load_milkroad(out_path))
    monkeypatch.setattr(fetch_fear_greed, "write_milkroad",
                        lambda data: write_milkroad(data, out_path))

    rc = fetch_fear_greed.main()
    assert rc == 0
    data = load_milkroad(out_path)
    assert data["indicators"]["fear_greed"]["value"] == 19
    assert data["indicators"]["fear_greed"]["label"] == "Extreme Fear"
    assert data["source"] == "alternative.me"
    assert not (Path(__file__).resolve().parent.parent / "data" / "milkroad.json").exists()


def test_main_handles_http_error(monkeypatch, capsys):
    monkeypatch.setattr(fetch_fear_greed, "requests",
                        Mock(get=Mock(return_value=_mock_resp(status=503))))
    rc = fetch_fear_greed.main()
    assert rc == 2
    assert "HTTP 503" in capsys.readouterr().err


def test_main_handles_unexpected_shape(monkeypatch, capsys):
    monkeypatch.setattr(fetch_fear_greed, "requests",
                        Mock(get=Mock(return_value=_mock_resp(body={"unexpected": True}))))
    rc = fetch_fear_greed.main()
    assert rc == 2
    assert "unexpected response shape" in capsys.readouterr().err
