"""Railgun / privacy hypothesis event study (report section 6).

Implements the pre-registered methodology:
  - beta-adjusted abnormal returns of a privacy basket vs. the benchmark
    (controls for the high-beta small-cap confound),
  - cumulative abnormal returns (CAR) in windows around dated privacy events,
  - permutation test (shuffle event dates) for significance — robust to
    fat tails, unlike a t-test,
  - drop-one-event robustness (does everything hinge on a single episode?).

The decision rule is fixed in advance (report section 6, step 4): trade only
if the effect survives the beta-matched control, permutation p < 0.05, the
drop-one test, and costs — and then cap at <= 5% of capital.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

WINDOWS = ((-5, 0), (0, 5), (0, 20))
P_THRESHOLD = 0.05


@dataclass
class EventStudyResult:
    windows: dict  # {"[a,b]": {"mean_car": ..., "p_value": ..., "n_events": ...}}
    drop_one: dict  # {"[a,b]": [mean_car excluding each event]}
    verdict: str

    def to_dict(self) -> dict:
        return {
            "windows": self.windows,
            "drop_one": self.drop_one,
            "verdict": self.verdict,
            "p_threshold": P_THRESHOLD,
        }


def beta_adjusted_abnormal(
    basket_closes: pd.DataFrame, bench_close: pd.Series, beta_window: int = 90
) -> pd.Series:
    """Daily abnormal return of the equal-weight basket vs. its rolling beta
    to the benchmark: abn_i = r_i - beta_i * r_bench, averaged across assets.
    """
    bench_ret = bench_close.pct_change()
    abns = {}
    for col in basket_closes.columns:
        r = basket_closes[col].pct_change()
        cov = r.rolling(beta_window, min_periods=beta_window).cov(bench_ret)
        var = bench_ret.rolling(beta_window, min_periods=beta_window).var()
        beta = (cov / var).shift(1)  # yesterday's beta: no lookahead
        abns[col] = r - beta * bench_ret
    return pd.DataFrame(abns).mean(axis=1).rename("abnormal")


def car_for_events(
    abnormal: pd.Series, events: list[pd.Timestamp], window: tuple[int, int]
) -> list[float]:
    """CAR of `abnormal` in [event+a, event+b] days for each event with data."""
    a, b = window
    out = []
    idx = abnormal.dropna().index
    for ev in events:
        ev = pd.Timestamp(ev)
        if ev.tz is None:
            ev = ev.tz_localize("UTC")
        pos = idx.searchsorted(ev)
        lo, hi = pos + a, pos + b + 1
        if lo < 0 or hi > len(idx) or pos >= len(idx):
            continue
        out.append(float(abnormal.loc[idx[lo:hi]].sum()))
    return out


def permutation_test(
    abnormal: pd.Series,
    events: list[pd.Timestamp],
    window: tuple[int, int],
    n_perm: int = 10_000,
    seed: int = 0,
) -> float:
    """One-sided p-value: probability that random event dates produce a mean
    CAR at least as large as the observed one."""
    observed = car_for_events(abnormal, events, window)
    if not observed:
        return float("nan")
    obs_mean = float(np.mean(observed))
    idx = abnormal.dropna().index
    a, b = window
    margin = max(abs(a), abs(b)) + 1
    valid = np.arange(margin, len(idx) - margin)
    rng = np.random.default_rng(seed)
    vals = abnormal.dropna().to_numpy()
    span = b - a + 1
    # Precompute rolling window sums for speed.
    csum = np.concatenate([[0.0], np.cumsum(vals)])
    hits = 0
    k = len(observed)
    for _ in range(n_perm):
        starts = rng.choice(valid, size=k, replace=False) + a
        cars = csum[starts + span] - csum[starts]
        if cars.mean() >= obs_mean:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def run_event_study(
    basket_closes: pd.DataFrame,
    bench_close: pd.Series,
    events: list,
    n_perm: int = 10_000,
    seed: int = 0,
) -> EventStudyResult:
    events = [pd.Timestamp(e, tz="UTC") if pd.Timestamp(e).tz is None else pd.Timestamp(e) for e in events]
    abnormal = beta_adjusted_abnormal(basket_closes, bench_close)
    windows, drop_one = {}, {}
    for w in WINDOWS:
        key = f"[{w[0]},{w[1]}]"
        cars = car_for_events(abnormal, events, w)
        p = permutation_test(abnormal, events, w, n_perm=n_perm, seed=seed)
        windows[key] = {
            "mean_car": float(np.mean(cars)) if cars else float("nan"),
            "p_value": float(p),
            "n_events": len(cars),
        }
        drops = []
        for i in range(len(events)):
            subset = events[:i] + events[i + 1 :]
            sub_cars = car_for_events(abnormal, subset, w)
            drops.append(float(np.mean(sub_cars)) if sub_cars else float("nan"))
        drop_one[key] = drops

    post = windows.get("[0,5]", {})
    significant = post.get("p_value", 1.0) < P_THRESHOLD and post.get("mean_car", 0) > 0
    drops_hold = all(d > 0 for d in drop_one.get("[0,5]", []) if not np.isnan(d))
    if significant and drops_hold:
        verdict = (
            "EFFECT DETECTED in [0,5] and robust to dropping any single event. "
            "Next gates before any capital: cost test on tradable venues, "
            "sub-period split, per-coin breakdown. Cap at 5% of capital."
        )
    elif significant:
        verdict = (
            "Effect in [0,5] is significant but NOT robust to dropping a single "
            "event — consistent with one episode driving everything. Do not trade."
        )
    else:
        verdict = (
            "No significant beta-adjusted effect. Consistent with the prior "
            "(~55% confounded artifact). Do not trade; archive the result."
        )
    return EventStudyResult(windows=windows, drop_one=drop_one, verdict=verdict)


def synthetic_study_data(days: int = 1200, n_events: int = 8, effect: float = 0.0, seed: int = 5):
    """Benchmark + 3-asset basket with optional injected post-event drift.

    effect > 0 plants a genuine effect (pipeline should detect it);
    effect = 0 is the null (pipeline should NOT cry signal).
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=days, freq="D", tz="UTC")
    bench_ret = rng.normal(0.0005, 0.03, days)
    bench = pd.Series(20_000 * np.exp(np.cumsum(bench_ret)), index=idx)
    basket = {}
    event_pos = np.sort(rng.choice(np.arange(120, days - 60), n_events, replace=False))
    events = [idx[p] for p in event_pos]
    for i in range(3):
        beta = 1.2 + 0.2 * i
        own = rng.normal(0, 0.04, days)
        r = beta * bench_ret + own
        if effect > 0:
            for p in event_pos:
                r[p : p + 5] += effect / 5
        basket[f"PRIV{i}"] = 100 * np.exp(np.cumsum(r))
    return pd.DataFrame(basket, index=idx), bench, events
