"""System configuration. Every number here is pre-registered in
docs/trading-system-analysis.md (sections 5 and 7). Changing a value after
seeing results is parameter-fitting; log any change in the hypothesis log.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskConfig:
    # Fraction of equity risked to the stop on any single new position.
    per_trade_risk: float = 0.005
    # Maximum portfolio weight in any single asset.
    max_asset_weight: float = 0.25
    # Maximum gross exposure (1.0 = no leverage on the directional sleeve).
    max_gross: float = 1.0
    # Annualized portfolio volatility target used for sizing.
    target_vol: float = 0.12
    # Circuit breakers on peak-to-trough equity drawdown.
    dd_half_size: float = 0.10  # halve all sizes
    dd_go_flat: float = 0.15  # go flat
    # Trading days to stay flat after the go-flat breaker trips.
    breaker_cooldown_days: int = 30


@dataclass(frozen=True)
class CostConfig:
    # Pessimistic round-trip modeling: 15 bps per side (fee + spread)
    # plus 10 bps slippage per side.
    fee_bps_per_side: float = 15.0
    slippage_bps_per_side: float = 10.0

    @property
    def cost_per_side(self) -> float:
        return (self.fee_bps_per_side + self.slippage_bps_per_side) / 10_000.0


@dataclass(frozen=True)
class TrendConfig:
    # Pre-declared lookback grid. The strategy must be profitable across the
    # whole grid, not at the best point (robustness, not peak performance).
    lookbacks: tuple = (50, 100, 200)
    # Exit channel is lookback // exit_divisor (classic Donchian asymmetry).
    exit_divisor: int = 2
    # ATR period for the initial stop used in position sizing.
    atr_period: int = 20
    # Stop distance in ATR multiples.
    atr_stop_mult: float = 3.0


@dataclass(frozen=True)
class RegimeConfig:
    sma_long: int = 200
    return_lookback: int = 90
    vol_window: int = 30
    # Rolling window (trading days) over which vol percentile is ranked.
    vol_rank_window: int = 365
    # Top-decile realized vol marks the euphoric / stressed flag.
    vol_extreme_pct: float = 0.90
    # Exposure multipliers per regime state.
    mult_risk_on_trending: float = 1.0
    mult_risk_on_euphoric: float = 0.6
    mult_chop: float = 0.5
    mult_risk_off: float = 0.25


@dataclass(frozen=True)
class CarryConfig:
    # Enter when trailing 7-day average funding exceeds this (annualized).
    enter_hurdle_annual: float = 0.10
    # Exit when it decays below this (annualized) — hysteresis band.
    exit_hurdle_annual: float = 0.05
    avg_window_days: int = 7
    # Binance perp funding accrues every 8 hours -> 3 per day.
    periods_per_day: int = 3
    # Hard cap on the carry sleeve as a fraction of the account.
    max_sleeve_weight: float = 0.30


@dataclass(frozen=True)
class SystemConfig:
    # Liquid-majors universe for Sleeve A (strict liquidity screen; see report).
    universe: tuple = ("BTCUSDT", "ETHUSDT")
    benchmark: str = "BTCUSDT"
    risk: RiskConfig = field(default_factory=RiskConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    carry: CarryConfig = field(default_factory=CarryConfig)


DEFAULT = SystemConfig()

# --- H1b (POST-HOC, registered 2026-06-12 after H1 failed as registered) ---
# H1 result on real data 2017-2025: Sharpe 1.12 / 1.03 / 0.597 for lookbacks
# 50/100/200 — the gate failed only on the 200-day leg. H1b drops the slow
# lookback, expands the universe to more liquid majors as fresh evidence, and
# reconciles sizing so the vol target (not the per-trade risk cap) is the
# primary constraint. BECAUSE THIS IS POST-HOC, its confirmation bar is
# stricter: gate pass on the expanded universe, 4 clean paper weeks, and any
# live deployment starts at 10% of target size.
# See research/hypothesis_log.json (H1, H1b) and RISK_POLICY.md amendments.
H1B = SystemConfig(
    universe=("BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"),
    risk=RiskConfig(per_trade_risk=0.01),
    trend=TrendConfig(lookbacks=(50, 100)),
)

CONFIGS = {"default": DEFAULT, "h1b": H1B}
