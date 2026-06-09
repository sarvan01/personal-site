"""Risk engine (report section 5) — built before any signal code, and every
weight the system trades passes through here.

Three layers:
  1. Per-asset sizing: volatility targeting, per-trade risk-to-stop cap,
     and a hard max single-asset weight.
  2. Portfolio: regime multiplier and a gross-exposure cap.
  3. Circuit breakers: stateful drawdown brakes on the live equity path.
"""

import pandas as pd

from .config import RiskConfig
from .indicators import realized_vol


def asset_weight(
    signal: float,
    asset_vol: float,
    price: float,
    stop_dist: float,
    cfg: RiskConfig,
) -> float:
    """Target weight for one asset given its signal and risk inputs."""
    if signal <= 0 or price <= 0:
        return 0.0
    # Volatility targeting: scale so the position contributes ~target_vol.
    vol_w = cfg.target_vol / asset_vol if asset_vol and asset_vol > 0 else 0.0
    # Per-trade risk: weight * (stop / price) must not exceed per_trade_risk.
    risk_w = (
        cfg.per_trade_risk / (stop_dist / price)
        if stop_dist and stop_dist > 0
        else 0.0
    )
    return float(min(vol_w, risk_w, cfg.max_asset_weight)) * signal


def target_weights(
    signals: pd.DataFrame,
    closes: pd.DataFrame,
    stops: pd.DataFrame,
    regime_mult: pd.Series,
    cfg: RiskConfig,
    vol_window: int = 30,
) -> pd.DataFrame:
    """Vectorized layer 1 + 2: per-asset sizing, regime scaling, gross cap."""
    vols = closes.apply(lambda s: realized_vol(s, vol_window))
    vol_w = (cfg.target_vol / vols).clip(upper=cfg.max_asset_weight)
    risk_w = (cfg.per_trade_risk / (stops / closes)).clip(upper=cfg.max_asset_weight)
    risk_w = risk_w.reindex_like(vol_w)
    weights = signals * vol_w.where(vol_w <= risk_w, risk_w)
    weights = weights.fillna(0.0).clip(lower=0.0, upper=cfg.max_asset_weight)
    weights = weights.mul(regime_mult.reindex(weights.index).fillna(0.0), axis=0)
    gross = weights.sum(axis=1)
    over = gross > cfg.max_gross
    weights[over] = weights[over].div(gross[over], axis=0).mul(cfg.max_gross)
    return weights


class CircuitBreaker:
    """Stateful drawdown brake, stepped forward one day at a time.

    -10% from peak equity: halve all sizes.
    -15% from peak equity: go flat for `breaker_cooldown_days`, then resume
    at half size until equity makes a new high.
    """

    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.peak = 0.0
        self.cooldown_left = 0
        self.recovering = False

    def step(self, equity: float) -> float:
        self.peak = max(self.peak, equity)
        dd = equity / self.peak - 1.0 if self.peak > 0 else 0.0

        if self.cooldown_left > 0:
            self.cooldown_left -= 1
            return 0.0

        if dd <= -self.cfg.dd_go_flat:
            self.cooldown_left = self.cfg.breaker_cooldown_days
            self.recovering = True
            return 0.0

        if self.recovering:
            if equity >= self.peak:
                self.recovering = False
            else:
                return 0.5

        if dd <= -self.cfg.dd_half_size:
            return 0.5
        return 1.0
