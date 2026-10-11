import numpy as np

from trading_system.config import RiskConfig
from trading_system.risk import CircuitBreaker, asset_weight


CFG = RiskConfig()


def test_flat_signal_means_zero_weight():
    assert asset_weight(0.0, 0.5, 100.0, 5.0, CFG) == 0.0


def test_weight_capped_by_max_asset_weight():
    # Tiny vol and a tight stop would otherwise produce a giant weight.
    w = asset_weight(1.0, 0.01, 100.0, 0.1, CFG)
    assert w == CFG.max_asset_weight


def test_per_trade_risk_cap_binds():
    # stop is 10% of price -> weight must be <= 0.5% / 10% = 5%.
    w = asset_weight(1.0, 0.5, 100.0, 10.0, CFG)
    assert w <= CFG.per_trade_risk / 0.10 + 1e-12
    # Implied risk-to-stop never exceeds the configured per-trade risk.
    assert w * (10.0 / 100.0) <= CFG.per_trade_risk + 1e-12


def test_vol_target_cap_binds():
    # High vol asset: weight limited to target_vol / asset_vol.
    w = asset_weight(1.0, 1.2, 100.0, 1.0, CFG)
    assert np.isclose(w, min(CFG.target_vol / 1.2, CFG.per_trade_risk / 0.01,
                             CFG.max_asset_weight))


def test_zero_stop_or_vol_is_safe():
    assert asset_weight(1.0, 0.0, 100.0, 5.0, CFG) == 0.0
    assert asset_weight(1.0, 0.5, 100.0, 0.0, CFG) == 0.0


def test_circuit_breaker_half_then_flat_then_cooldown():
    cfg = RiskConfig(breaker_cooldown_days=3)
    cb = CircuitBreaker(cfg)
    assert cb.step(100.0) == 1.0  # at peak
    assert cb.step(91.0) == 1.0  # -9% is inside the first breaker
    cb2 = CircuitBreaker(cfg)
    cb2.step(100.0)
    assert cb2.step(89.0) == 0.5  # -11% -> half size
    assert cb2.step(84.0) == 0.0  # -16% -> flat, cooldown starts
    assert cb2.step(84.0) == 0.0  # cooldown day 1
    assert cb2.step(84.0) == 0.0  # cooldown day 2
    assert cb2.step(84.0) == 0.0  # cooldown day 3
    assert cb2.step(95.0) == 0.5  # recovering: half size until new high
    assert cb2.step(101.0) == 1.0  # new equity high -> full size


def test_circuit_breaker_minor_drawdown_keeps_full_size():
    cb = CircuitBreaker(RiskConfig())
    cb.step(100.0)
    assert cb.step(95.0) == 1.0  # -5% is normal noise
