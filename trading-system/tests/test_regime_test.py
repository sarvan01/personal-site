import numpy as np
import pandas as pd

from trading_system.event_study import synthetic_study_data
from trading_system.regime_test import (
    crypto_stress_regime,
    run_regime_test,
    vix_risk_off_regime,
)


def _vix_for(index, high_frac=0.2, seed=0):
    rng = np.random.default_rng(seed)
    vals = np.where(rng.random(len(index)) < high_frac,
                    rng.uniform(26, 45, len(index)),
                    rng.uniform(12, 24, len(index)))
    return pd.Series(vals, index=index, name="close")


def test_crypto_stress_mask_is_boolean_and_lagged():
    basket, bench, _ = synthetic_study_data(seed=2)
    mask = crypto_stress_regime(bench)
    assert mask.dtype == bool
    assert len(mask) == len(bench)
    # First value must be False (shifted; no lookahead from day 0).
    assert mask.iloc[0] == False  # noqa: E712


def test_vix_mask_threshold():
    idx = pd.date_range("2022-01-01", periods=10, freq="D", tz="UTC")
    vix = pd.Series([10, 30, 30, 10, 10, 40, 10, 10, 10, 10], index=idx, name="close")
    mask = vix_risk_off_regime(vix, threshold=25)
    # Day after a >25 reading is flagged (shift(1)).
    assert mask.iloc[2] == True   # noqa: E712  (prior day VIX=30)
    assert mask.iloc[0] == False  # noqa: E712


def test_null_regime_has_no_significant_effect():
    # No injected effect -> in-regime abnormal return should not be
    # significantly positive.
    basket, bench, _ = synthetic_study_data(effect=0.0, seed=7)
    res = run_regime_test(basket, bench, crypto_stress_regime(bench),
                          "U2", "crypto stress", n_perm=400, seed=1)
    assert res.p_value > 0.05
    assert res.n_in > 0 and res.n_out > 0
    assert "U2" in res.verdict


def test_injected_in_regime_outperformance_is_detected():
    # Build a basket that outperforms specifically on high-VIX days.
    idx = pd.date_range("2021-01-01", periods=900, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    bench_ret = rng.normal(0.0, 0.03, len(idx))
    bench = pd.Series(20_000 * np.exp(np.cumsum(bench_ret)), index=idx)
    vix = _vix_for(idx, high_frac=0.25, seed=3)
    # The regime mask uses PRIOR-day VIX (no lookahead), so inject the
    # outperformance on the days the mask actually flags.
    flagged = vix_risk_off_regime(vix).to_numpy()
    cols = {}
    for i in range(3):
        r = 1.2 * bench_ret + rng.normal(0, 0.03, len(idx))
        r[flagged] += 0.02  # +2%/day extra on flagged risk-off days
        cols[f"PRIV{i}"] = 100 * np.exp(np.cumsum(r))
    basket = pd.DataFrame(cols, index=idx)
    res = run_regime_test(basket, bench, vix_risk_off_regime(vix),
                          "U1", "VIX>25", n_perm=400, seed=1)
    assert res.diff > 0
    assert res.p_value < 0.05
    assert "OUTPERFORMS" in res.verdict
