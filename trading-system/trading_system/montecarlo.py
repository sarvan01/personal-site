"""Forward-looking expectation setting via block bootstrap (the honest kind
of "prediction": a distribution over outcomes, not a point forecast).

Resamples the backtest's own daily strategy returns in contiguous blocks
(preserving short-range autocorrelation and vol clustering that i.i.d.
resampling would destroy) to build N simulated forward years, then reports
return percentiles, max-drawdown percentiles, and the probability of hitting
each circuit-breaker level.

Caveat baked into the output: the bootstrap only reshuffles history it has
seen. It cannot produce a regime worse than the worst block in the sample,
so treat the tails as optimistic lower bounds on how bad things can get.
"""

import numpy as np
import pandas as pd

from .indicators import drawdown


def block_bootstrap_paths(
    daily_returns: np.ndarray,
    n_paths: int = 2000,
    horizon: int = 365,
    block: int = 20,
    seed: int = 0,
) -> np.ndarray:
    """(n_paths, horizon) matrix of resampled daily-return paths."""
    rng = np.random.default_rng(seed)
    n = len(daily_returns)
    if n < block * 2:
        raise ValueError(f"need at least {block * 2} return observations, got {n}")
    blocks_per_path = int(np.ceil(horizon / block))
    starts = rng.integers(0, n - block, size=(n_paths, blocks_per_path))
    # Gather blocks: shape (n_paths, blocks_per_path, block) -> flatten -> trim.
    idx = starts[:, :, None] + np.arange(block)[None, None, :]
    paths = daily_returns[idx].reshape(n_paths, -1)[:, :horizon]
    return paths


def forward_distribution(
    equity: pd.Series,
    n_paths: int = 2000,
    horizon: int = 365,
    block: int = 20,
    seed: int = 0,
    dd_levels: tuple = (0.10, 0.15),
) -> dict:
    """One-year-forward outcome distribution from a backtest equity curve."""
    rets = equity.pct_change().dropna().to_numpy()
    paths = block_bootstrap_paths(rets, n_paths, horizon, block, seed)
    growth = np.cumprod(1.0 + paths, axis=1)
    final = growth[:, -1] - 1.0

    peaks = np.maximum.accumulate(growth, axis=1)
    dds = growth / peaks - 1.0
    max_dd = dds.min(axis=1)

    pct = lambda a, q: float(np.percentile(a, q))
    out = {
        "n_paths": n_paths,
        "horizon_days": horizon,
        "block_days": block,
        "return_1y": {f"p{q}": pct(final, q) for q in (5, 25, 50, 75, 95)},
        "max_drawdown_1y": {f"p{q}": pct(max_dd, q) for q in (5, 50, 95)},
        "prob_positive_year": float((final > 0).mean()),
    }
    for lvl in dd_levels:
        out[f"prob_dd_exceeds_{int(lvl * 100)}pct"] = float((max_dd <= -lvl).mean())
    out["caveat"] = ("bootstrap of observed history; cannot simulate regimes "
                     "worse than the worst sampled block -- tails are optimistic")
    return out
