import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.montecarlo import block_bootstrap_paths, forward_distribution


def _equity(days=800, mu=0.0005, sigma=0.01, seed=3):
    rng = np.random.default_rng(seed)
    rets = rng.normal(mu, sigma, days)
    idx = pd.date_range("2023-01-01", periods=days, freq="D", tz="UTC")
    return pd.Series(100_000 * np.cumprod(1 + rets), index=idx)


def test_paths_shape_and_determinism():
    rets = _equity().pct_change().dropna().to_numpy()
    a = block_bootstrap_paths(rets, n_paths=50, horizon=100, seed=1)
    b = block_bootstrap_paths(rets, n_paths=50, horizon=100, seed=1)
    assert a.shape == (50, 100)
    assert np.array_equal(a, b)  # same seed -> same paths (resumable/reproducible)
    c = block_bootstrap_paths(rets, n_paths=50, horizon=100, seed=2)
    assert not np.array_equal(a, c)


def test_paths_only_contain_observed_returns():
    rets = np.array([0.01, -0.02, 0.03] * 30)
    paths = block_bootstrap_paths(rets, n_paths=10, horizon=30, block=5, seed=0)
    assert set(np.round(paths.flatten(), 10)) <= set(np.round(rets, 10))


def test_too_short_history_raises():
    with pytest.raises(ValueError, match="at least"):
        block_bootstrap_paths(np.zeros(10), block=20)


def test_zero_returns_give_zero_distribution():
    eq = pd.Series(np.full(200, 100.0),
                   index=pd.date_range("2024-01-01", periods=200, freq="D"))
    out = forward_distribution(eq, n_paths=100, horizon=50)
    assert out["return_1y"]["p50"] == pytest.approx(0.0)
    assert out["prob_dd_exceeds_15pct"] == 0.0


def test_positive_drift_median_positive_and_probs_bounded():
    out = forward_distribution(_equity(mu=0.001), n_paths=300, horizon=252, seed=1)
    assert out["return_1y"]["p50"] > 0
    assert out["return_1y"]["p5"] < out["return_1y"]["p50"] < out["return_1y"]["p95"]
    for k in ("prob_positive_year", "prob_dd_exceeds_10pct", "prob_dd_exceeds_15pct"):
        assert 0.0 <= out[k] <= 1.0
    # Drawdown percentiles are non-positive by construction.
    assert out["max_drawdown_1y"]["p5"] <= out["max_drawdown_1y"]["p95"] <= 0.0


def test_volatile_series_hits_breakers_more_often():
    calm = forward_distribution(_equity(sigma=0.003, seed=5), n_paths=200, seed=1)
    wild = forward_distribution(_equity(sigma=0.03, seed=5), n_paths=200, seed=1)
    assert wild["prob_dd_exceeds_15pct"] > calm["prob_dd_exceeds_15pct"]
