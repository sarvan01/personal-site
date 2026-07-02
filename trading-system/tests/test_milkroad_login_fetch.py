import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "feeds"))

import fetch_milkroad_login as fml  # noqa: E402

from trading_system.milkroad import load_milkroad, write_milkroad  # noqa: E402

LOGIN_CFG = {"login_url": "https://milkroad.com/api/login",
            "email_field": "email", "password_field": "password"}


def _mock_resp(status=200, body=None, cookies=None):
    r = Mock()
    r.status_code = status
    r.json.return_value = body or {}
    r.text = str(body)
    return r


def _session_with_cookies(cookies):
    s = Mock()
    s.cookies = cookies
    return s


# --------------------------------------------------------------------------
# login()
# --------------------------------------------------------------------------
def test_login_success_sets_no_exception():
    session = _session_with_cookies({"session_id": "abc123"})
    session.post.return_value = _mock_resp(status=200)
    fml.login(LOGIN_CFG, session, debug=False, email="a@b.com", password="hunter2")
    session.post.assert_called_once()
    _, kwargs = session.post.call_args
    assert kwargs["json"] == {"email": "a@b.com", "password": "hunter2"}


def test_login_uses_form_encoding_when_configured():
    session = _session_with_cookies({"session_id": "abc"})
    session.post.return_value = _mock_resp(status=200)
    cfg = {**LOGIN_CFG, "content_type": "form"}
    fml.login(cfg, session, debug=False, email="a@b.com", password="hunter2")
    _, kwargs = session.post.call_args
    assert "data" in kwargs and "json" not in kwargs


def test_login_includes_extra_fields():
    session = _session_with_cookies({"s": "1"})
    session.post.return_value = _mock_resp(status=200)
    cfg = {**LOGIN_CFG, "extra_fields": {"remember": True}}
    fml.login(cfg, session, debug=False, email="a@b.com", password="x")
    _, kwargs = session.post.call_args
    assert kwargs["json"]["remember"] is True


def test_login_http_error_raises():
    session = _session_with_cookies({})
    session.post.return_value = _mock_resp(status=401)
    with pytest.raises(fml.LoginError, match="401"):
        fml.login(LOGIN_CFG, session, debug=False, email="a@b.com", password="x")


def test_login_no_cookies_raises():
    session = _session_with_cookies({})  # empty -- login "succeeded" but no session
    session.post.return_value = _mock_resp(status=200)
    with pytest.raises(fml.LoginError, match="no session cookie"):
        fml.login(LOGIN_CFG, session, debug=False, email="a@b.com", password="x")


def test_login_network_failure_raises():
    import requests
    session = _session_with_cookies({})
    session.post.side_effect = requests.RequestException("timed out")
    with pytest.raises(fml.LoginError, match="timed out"):
        fml.login(LOGIN_CFG, session, debug=False, email="a@b.com", password="x")


def test_password_never_printed(capsys):
    session = _session_with_cookies({"s": "1"})
    session.post.return_value = _mock_resp(status=200)
    fml.login(LOGIN_CFG, session, debug=True, email="a@b.com", password="super-secret-pw")
    out = capsys.readouterr()
    assert "super-secret-pw" not in out.out
    assert "super-secret-pw" not in out.err


# --------------------------------------------------------------------------
# fetch_indicators()
# --------------------------------------------------------------------------
def test_fetch_indicators_missing_config_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(fml, "INDICATORS_CONFIG_PATH", tmp_path / "nope.json")
    session = Mock()
    assert fml.fetch_indicators(session, debug=False) == {}


def test_fetch_indicators_parses_configured_path(monkeypatch, tmp_path):
    cfg_path = tmp_path / "endpoints.json"
    cfg_path.write_text('{"macro_index": {"url": "https://x/y", '
                        '"value_path": "data.score", "label_path": "data.label"}}')
    monkeypatch.setattr(fml, "INDICATORS_CONFIG_PATH", cfg_path)
    session = Mock()
    session.get.return_value = _mock_resp(body={"data": {"score": 0.29, "label": "Risk On"}})
    result = fml.fetch_indicators(session, debug=False)
    assert result["macro_index"]["value"] == 0.29
    assert result["macro_index"]["label"] == "Risk On"


# --------------------------------------------------------------------------
# fetch_trades()
# --------------------------------------------------------------------------
def test_fetch_trades_missing_config_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(fml, "TRADES_CONFIG_PATH", tmp_path / "nope.json")
    assert fml.fetch_trades(Mock(), debug=False) == []


def test_fetch_trades_parses_records_and_optional_fields(monkeypatch, tmp_path):
    cfg_path = tmp_path / "trades.json"
    cfg_path.write_text('''{
        "url": "https://x/trades", "records_path": "data",
        "date_path": "date", "analyst_path": "analyst", "action_path": "type",
        "asset_path": "asset", "note_path": "rationale", "perf_path": "perf"
    }''')
    monkeypatch.setattr(fml, "TRADES_CONFIG_PATH", cfg_path)
    session = Mock()
    session.get.return_value = _mock_resp(body={"data": [
        {"date": "2026-07-01T11:12:00Z", "analyst": "Melvin", "type": "sell",
         "asset": "MU", "rationale": "trimming exposure", "perf": 144.94},
        {"date": "2026-06-30", "analyst": "John", "type": "buy",
         "asset": "BTC", "rationale": "buying the lows", "perf": None},
    ]})
    trades = fml.fetch_trades(session, debug=False)
    assert len(trades) == 2
    assert trades[0]["date"] == "2026-07-01"
    assert trades[0]["action"] == "SELL"
    assert trades[0]["analyst"] == "Melvin"
    assert trades[0]["perf_pct"] == 144.94
    assert "perf_pct" not in trades[1]  # None perf -> field omitted, not crashed


def test_fetch_trades_skips_incomplete_records(monkeypatch, tmp_path):
    cfg_path = tmp_path / "trades.json"
    cfg_path.write_text('{"url": "https://x/trades", "records_path": "data", '
                        '"date_path": "date", "action_path": "type", "asset_path": "asset"}')
    monkeypatch.setattr(fml, "TRADES_CONFIG_PATH", cfg_path)
    session = Mock()
    session.get.return_value = _mock_resp(body={"data": [
        {"date": "2026-07-01", "type": "BUY"},  # missing asset -> skipped
        {"date": "2026-07-01", "type": "BUY", "asset": "BTC"},  # complete -> kept
    ]})
    trades = fml.fetch_trades(session, debug=False)
    assert len(trades) == 1
    assert trades[0]["asset"] == "BTC"


def test_fetch_trades_non_list_records_path_is_safe(monkeypatch, tmp_path):
    cfg_path = tmp_path / "trades.json"
    cfg_path.write_text('{"url": "https://x/trades", "records_path": "data.notalist"}')
    monkeypatch.setattr(fml, "TRADES_CONFIG_PATH", cfg_path)
    session = Mock()
    session.get.return_value = _mock_resp(body={"data": {"notalist": "oops"}})
    assert fml.fetch_trades(session, debug=False) == []


# --------------------------------------------------------------------------
# load_required_config()
# --------------------------------------------------------------------------
def test_load_required_config_missing_file_raises(tmp_path):
    with pytest.raises(fml.LoginError, match="not found"):
        fml.load_required_config(tmp_path / "nope.json", tmp_path / "nope.sample.json", "login")


# --------------------------------------------------------------------------
# main() -- end to end with everything mocked, isolated from real files
# --------------------------------------------------------------------------
def test_main_end_to_end(tmp_path, monkeypatch, capsys):
    login_cfg_path = tmp_path / "login.json"
    login_cfg_path.write_text(
        '{"login_url": "https://milkroad.com/api/login", "email_field": "email", '
        '"password_field": "password"}'
    )
    monkeypatch.setattr(fml, "LOGIN_CONFIG_PATH", login_cfg_path)
    monkeypatch.setattr(fml, "INDICATORS_CONFIG_PATH", tmp_path / "no_indicators.json")
    monkeypatch.setattr(fml, "TRADES_CONFIG_PATH", tmp_path / "no_trades.json")

    out_path = tmp_path / "milkroad.json"
    monkeypatch.setattr(fml, "load_milkroad", lambda: load_milkroad(out_path))
    monkeypatch.setattr(fml, "write_milkroad", lambda data: write_milkroad(data, out_path))

    fake_session = _session_with_cookies({"session_id": "abc"})
    fake_session.post.return_value = _mock_resp(status=200)
    monkeypatch.setattr(fml.requests, "Session", lambda: fake_session)
    monkeypatch.setattr("builtins.input", lambda *_: "me@example.com")
    monkeypatch.setattr(fml.getpass, "getpass", lambda *_: "hunter2")
    monkeypatch.setattr(fml, "fetch_indicators", lambda s, d: {"macro_index": {"value": 1, "label": "x", "as_of": "2026-01-01"}})
    monkeypatch.setattr(fml, "fetch_trades", lambda s, d: [])
    monkeypatch.setattr(sys, "argv", ["fetch_milkroad_login.py"])

    rc = fml.main()
    assert rc == 0
    data = load_milkroad(out_path)
    assert data["indicators"]["macro_index"]["value"] == 1
    assert data["source"] == "milkroad.com"
    assert "hunter2" not in capsys.readouterr().out
    assert not (Path(__file__).resolve().parent.parent / "data" / "milkroad.json").exists()


def test_main_reports_login_error_cleanly(tmp_path, monkeypatch, capsys):
    login_cfg_path = tmp_path / "login.json"
    login_cfg_path.write_text('{"login_url": "https://x/login"}')
    monkeypatch.setattr(fml, "LOGIN_CONFIG_PATH", login_cfg_path)
    monkeypatch.setattr("builtins.input", lambda *_: "me@example.com")
    monkeypatch.setattr(fml.getpass, "getpass", lambda *_: "wrongpass")
    fake_session = _session_with_cookies({})
    fake_session.post.return_value = _mock_resp(status=403)
    monkeypatch.setattr(fml.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(sys, "argv", ["fetch_milkroad_login.py"])

    rc = fml.main()
    assert rc == 3
    assert "403" in capsys.readouterr().err
