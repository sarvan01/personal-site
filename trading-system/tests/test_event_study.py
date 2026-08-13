import numpy as np

from trading_system.event_study import (
    beta_adjusted_abnormal,
    run_event_study,
    synthetic_study_data,
)


def test_abnormal_returns_remove_beta():
    basket, bench, _ = synthetic_study_data(effect=0.0, seed=3)
    abn = beta_adjusted_abnormal(basket, bench).dropna()
    bench_ret = bench.pct_change().reindex(abn.index)
    # After beta adjustment, residual correlation with the benchmark ~ 0.
    assert abs(abn.corr(bench_ret)) < 0.15


def test_null_data_yields_no_significance():
    basket, bench, events = synthetic_study_data(effect=0.0, seed=3)
    result = run_event_study(basket, bench, events, n_perm=500, seed=1)
    assert result.windows["[0,5]"]["p_value"] > 0.05
    assert "Do not trade" in result.verdict


def test_injected_effect_is_detected():
    # Plant a +8% abnormal drift over the 5 days after each event.
    basket, bench, events = synthetic_study_data(effect=0.08, seed=3)
    result = run_event_study(basket, bench, events, n_perm=500, seed=1)
    assert result.windows["[0,5]"]["p_value"] < 0.05
    assert result.windows["[0,5]"]["mean_car"] > 0


def test_drop_one_robustness_reported():
    basket, bench, events = synthetic_study_data(effect=0.08, seed=3)
    result = run_event_study(basket, bench, events, n_perm=200, seed=1)
    drops = result.drop_one["[0,5]"]
    assert len(drops) == len(events)
    assert all(not np.isnan(d) for d in drops)
