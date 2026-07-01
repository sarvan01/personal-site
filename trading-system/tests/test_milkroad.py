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
    assert set(m["indicators"]) == {"macro_index", "macro_pulse", "crypto_pulse"}
    assert all("value" in v for v in m["indicators"].values())
    assert isinstance(m["trades"], list) and m["trades"]


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
