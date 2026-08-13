import json

from trading_system.cockpit import build_cockpit
from trading_system.milkroad import (
    load_milkroad,
    merge_milkroad,
    sample_milkroad,
    write_milkroad,
)


def test_sample_has_expected_shape():
    m = sample_milkroad()
    assert set(m["indicators"]) == {"macro_index", "macro_pulse", "crypto_pulse", "fear_greed"}
    assert all("value" in v for v in m["indicators"].values())
    assert isinstance(m["trades"], list) and m["trades"]
    # macro_index demonstrates a non-0..100 range via min/max.
    assert m["indicators"]["macro_index"]["min"] == -3
    assert m["indicators"]["macro_index"]["max"] == 3


def test_load_missing_returns_none(tmp_path):
    assert load_milkroad(tmp_path / "nope.json") is None


def test_write_and_load_roundtrip(tmp_path):
    p = tmp_path / "milkroad.json"
    write_milkroad(sample_milkroad(), p)
    loaded = load_milkroad(p)
    assert loaded["indicators"]["crypto_pulse"]["value"] == 71
    assert "updated_utc" in loaded  # stamped on write


def test_load_bad_json_is_safe(tmp_path):
    p = tmp_path / "milkroad.json"
    p.write_text("{ not valid json")
    assert load_milkroad(p) is None


def test_merge_keeps_both_sections():
    base = {"indicators": {"macro_index": {"value": 60}}, "trades": [{"asset": "BTC"}]}
    # Discord update fills trades only — must not wipe indicators.
    merged = merge_milkroad(base, {"trades": [{"asset": "SOL"}], "source": "discord"})
    assert merged["indicators"]["macro_index"]["value"] == 60
    assert merged["trades"][0]["asset"] == "SOL"
    # Indicators update fills indicators only — must not wipe trades.
    merged2 = merge_milkroad(merged, {"indicators": {"crypto_pulse": {"value": 70}}})
    assert merged2["trades"][0]["asset"] == "SOL"
    assert merged2["indicators"]["crypto_pulse"]["value"] == 70


def test_cockpit_renders_milkroad_panel_as_context(tmp_path):
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={"BTCUSDT": {"signal": True, "close": 50000.0, "target_weight": 0.05}},
        carry={"signal": "OUT", "trailing_7d_funding_annualized": 0.04},
        risk={"per_trade_risk": 0.005},
        milkroad=sample_milkroad(),
        data_mode="synthetic",
        out_dir=tmp_path,
    )
    html = path.read_text()
    assert "Milk Road" in html
    assert "not a trading signal" in html.lower()
    assert "crypto pulse" in html.lower()
    assert "SOL" in html  # a sample trade rendered


def test_cockpit_omits_panel_when_no_milkroad(tmp_path):
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={},
        carry={"signal": "OUT"},
        risk={},
        milkroad=None,
        data_mode="synthetic",
        out_dir=tmp_path,
    )
    assert "Milk Road" not in path.read_text()


def test_cockpit_normalizes_non_0_100_indicator_range(tmp_path):
    # Milk Road's Macro Index runs -3..+3, not 0-100. value=0.29 on that
    # range should normalize to (0.29 - -3) / 6 * 100 = ~54.8% -> "55%",
    # NOT be clamped near-zero as it would if treated as a 0-100 value.
    m = sample_milkroad()
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={}, carry={"signal": "OUT"}, risk={},
        milkroad=m, data_mode="synthetic", out_dir=tmp_path,
    )
    html = path.read_text()
    assert "width:55%" in html
    assert "0.29" in html


def test_cockpit_shows_fear_greed_indicator(tmp_path):
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={}, carry={"signal": "OUT"}, risk={},
        milkroad=sample_milkroad(), data_mode="synthetic", out_dir=tmp_path,
    )
    html = path.read_text()
    assert "fear greed" in html.lower()
    assert "Extreme Fear" in html


def test_trades_table_shows_analyst_and_perf_when_present(tmp_path):
    m = {
        "indicators": {},
        "trades": [
            {"date": "2026-07-01", "action": "SELL", "asset": "MU", "note": "",
             "analyst": "Melvin", "perf_pct": 144.94},
        ],
    }
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={}, carry={"signal": "OUT"}, risk={},
        milkroad=m, data_mode="synthetic", out_dir=tmp_path,
    )
    html = path.read_text()
    assert "Melvin" in html
    assert "+144.9%" in html
    assert "<th>analyst</th>" in html
    assert "<th>perf</th>" in html


def test_trades_table_omits_optional_columns_when_absent(tmp_path):
    # Plain manual/Discord-style trades (no analyst/perf_pct) must not grow
    # empty columns.
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={}, carry={"signal": "OUT"}, risk={},
        milkroad={"indicators": {}, "trades": [
            {"date": "2026-07-01", "action": "HOLD", "asset": "BTC", "note": ""}
        ]},
        data_mode="synthetic", out_dir=tmp_path,
    )
    html = path.read_text()
    assert "<th>analyst</th>" not in html
    assert "<th>perf</th>" not in html


def test_cockpit_html_is_valid_utf8_with_em_dashes(tmp_path):
    # Windows locale default (cp1252) garbled the em-dashes into replacement
    # chars in the browser; the file must be explicit UTF-8.
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={}, carry={"signal": "OUT"}, risk={},
        data_mode="synthetic", out_dir=tmp_path,
    )
    raw = path.read_bytes()
    assert "—".encode("utf-8") in raw  # em-dash present as proper UTF-8 bytes
    raw.decode("utf-8")  # decodes cleanly
