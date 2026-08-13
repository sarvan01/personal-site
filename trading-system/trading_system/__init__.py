"""Two-sleeve trading system MVP.

Implements the system designed in docs/trading-system-analysis.md:
  - Sleeve A: regime-filtered trend-following on liquid crypto majors
  - Sleeve B: delta-neutral funding-rate carry monitor
  - Risk engine: vol targeting, per-trade risk caps, drawdown circuit breakers
  - Backtest harness: daily bars, pessimistic costs, walk-forward validation

This MVP generates signals and backtests only. It places NO live orders.
"""

__version__ = "0.1.0"
