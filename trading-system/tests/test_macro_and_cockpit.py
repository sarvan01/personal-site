from trading_system.cockpit import build_cockpit
from trading_system.config import DEFAULT
from trading_system.macro import macro_risk_off, synthetic_macro
from trading_system.regime import classify


def test_macro_composite_is_boolean_and_aligned(btc):
    dxy, ry, stables = synthetic_macro()
    flag = macro_risk_off(dxy, ry, stables, index=btc.index)
    assert flag is not None
    assert flag.dtype == bool
    assert len(flag) == len(btc)


def test_macro_returns_none_without_inputs():
    assert macro_risk_off() is None


def test_regime_accepts_macro_flag(btc):
    dxy, ry, stables = synthetic_macro()
    flag = macro_risk_off(dxy, ry, stables, index=btc.index)
    base = classify(btc["close"], DEFAULT.regime)
    with_macro = classify(btc["close"], DEFAULT.regime, macro_risk_off=flag)
    # Macro risk-off can only reduce or keep the multiplier, never raise it.
    assert (with_macro["multiplier"] <= base["multiplier"] + 1e-12).all()


def test_cockpit_renders_all_sections(tmp_path):
    path = build_cockpit(
        regime={"state": "chop", "exposure_multiplier": 0.5},
        signals={"BTCUSDT": {"signal": True, "close": 50000.0, "target_weight": 0.05}},
        carry={"signal": "OUT", "trailing_7d_funding_annualized": 0.04},
        risk={"per_trade_risk": 0.005},
        paper={"equity": 100000.0, "drawdown": -0.01},
        equity_history=[100000.0, 100100.0, 100050.0],
        backtest={"pass": False, "grid": [{"lookback": 100, "sharpe": 0.5}], "walk_forward": []},
        event_study={"windows": {"[0,5]": {"mean_car": 0.01, "p_value": 0.3, "n_events": 8}}, "verdict": "Do not trade"},
        reconciliation={"n_fills": 1, "n_with_observed_costs": 0},
        data_mode="synthetic",
        out_dir=tmp_path,
    )
    html = path.read_text()
    for needle in (
        "Cockpit", "Regime", "trend signals", "funding carry", "Risk limits",
        "Paper account", "Equity curve", "FAIL", "event study", "Hypothesis log",
        "plan progress", "No live orders",
    ):
        assert needle in html, f"missing section: {needle}"
