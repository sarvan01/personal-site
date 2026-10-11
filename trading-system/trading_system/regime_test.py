"""Privacy-basket regime tests U1 and U2 (report section 6).

Complements the event study (U3) with the two *regime* tests the methodology
defined but had not implemented:

  U1 — macro risk-off:  VIX > 25 (prior day's close).
  U2 — crypto stress:   BTC 30-day realized vol in its top quintile,
                        OR BTC drawdown > 20% from its 90-day high.

Method: difference-in-differences on the SAME beta-adjusted abnormal return
used by the event study (privacy basket minus its rolling beta to BTC). We
compare mean daily abnormal return INSIDE the regime vs OUTSIDE it. If the
Railgun thesis ("privacy outperforms in uncertainty") were true, the in-regime
mean abnormal return would be reliably positive and larger than out-of-regime.

Significance uses a permutation test on the regime labels (shuffle which days
are 'in regime', preserving the count), which is robust to the fat tails and
volatility clustering of crypto returns — unlike a plain t-test.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .event_study import beta_adjusted_abnormal

P_THRESHOLD = 0.05


@dataclass
class RegimeTestResult:
    label: str  # "U1" / "U2"
    description: str
    in_regime_mean: float
    out_regime_mean: float
    diff: float  # in - out (positive => outperforms in the regime)
    p_value: float
    n_in: int
    n_out: int
    verdict: str

    def to_dict(self) -> dict:
        return {
            "test": self.label,
            "regime": self.description,
            "in_regime_mean_daily": self.in_regime_mean,
            "out_regime_mean_daily": self.out_regime_mean,
            "diff": self.diff,
            "p_value": self.p_value,
            "n_in": self.n_in,
            "n_out": self.n_out,
            "verdict": self.verdict,
        }


def crypto_stress_regime(
    btc_close: pd.Series, vol_window: int = 30, dd_window: int = 90
) -> pd.Series:
    """U2 mask: BTC 30d realized vol in its top quintile OR drawdown > 20%
    from the 90-day high. Shifted one day (uses only prior-day information)."""
    logret = np.log(btc_close / btc_close.shift(1))
    rvol = logret.rolling(vol_window, min_periods=vol_window).std() * np.sqrt(365)
    hi_vol = rvol > rvol.rolling(365, min_periods=180).quantile(0.80)
    roll_high = btc_close.rolling(dd_window, min_periods=dd_window).max()
    deep_dd = (btc_close / roll_high - 1.0) < -0.20
    # shift with fill_value keeps a clean bool dtype (no fillna downcast).
    return (hi_vol | deep_dd).shift(1, fill_value=False).astype(bool)


def vix_risk_off_regime(vix: pd.Series, threshold: float = 25.0) -> pd.Series:
    """U1 mask: VIX above threshold on the prior day's close."""
    return (vix > threshold).shift(1, fill_value=False).astype(bool)


def _permutation_diff_p(
    abnormal: np.ndarray, mask: np.ndarray, observed_diff: float,
    n_perm: int, seed: int,
) -> float:
    """One-sided p: P(shuffled in-minus-out diff >= observed). Tests the
    Railgun direction (privacy OUTPERFORMS in the regime)."""
    rng = np.random.default_rng(seed)
    n_in = int(mask.sum())
    if n_in == 0 or n_in == len(mask):
        return float("nan")
    hits = 0
    total = abnormal.sum()
    for _ in range(n_perm):
        idx = rng.permutation(len(abnormal))[:n_in]
        in_mean = abnormal[idx].mean()
        out_mean = (total - abnormal[idx].sum()) / (len(abnormal) - n_in)
        if (in_mean - out_mean) >= observed_diff:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def run_regime_test(
    basket_closes: pd.DataFrame,
    btc_close: pd.Series,
    regime_mask: pd.Series,
    label: str,
    description: str,
    n_perm: int = 10_000,
    seed: int = 0,
) -> RegimeTestResult:
    abnormal = beta_adjusted_abnormal(basket_closes, btc_close).dropna()
    mask = regime_mask.reindex(abnormal.index).fillna(False).astype(bool)
    a = abnormal.to_numpy()
    m = mask.to_numpy()

    in_vals, out_vals = a[m], a[~m]
    in_mean = float(in_vals.mean()) if in_vals.size else float("nan")
    out_mean = float(out_vals.mean()) if out_vals.size else float("nan")
    diff = in_mean - out_mean
    p = _permutation_diff_p(a, m, diff, n_perm=n_perm, seed=seed)

    significant = (p < P_THRESHOLD) and (diff > 0)
    if significant:
        verdict = (f"{label}: privacy OUTPERFORMS in regime by {diff:+.3%}/day "
                   f"(p={p:.3f}). Survives — proceed to cost/sub-period gates, cap 5%.")
    elif diff > 0:
        verdict = (f"{label}: positive but NOT significant ({diff:+.3%}/day, "
                   f"p={p:.3f}). No edge.")
    else:
        verdict = (f"{label}: privacy UNDERPERFORMS in regime ({diff:+.3%}/day, "
                   f"p={p:.3f}). Thesis rejected for this regime.")
    return RegimeTestResult(
        label=label, description=description, in_regime_mean=in_mean,
        out_regime_mean=out_mean, diff=diff, p_value=float(p),
        n_in=int(m.sum()), n_out=int((~m).sum()), verdict=verdict,
    )
