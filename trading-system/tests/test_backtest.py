import numpy as np
import pandas as pd

from trading_system.backtest import run_backtest, run_grid, walk_forward
from trading_system.config import DEFAULT, CostConfig, SystemConfig
from trading_system.data import synthetic_klines


def test_backtest_runs_and_reports_metrics(btc, eth):
    res = run_backtest({"BTCUSDT": btc, "ETHUSDT": eth}, DEFAULT, lookback=100)
    m = res.metrics
    for key in ("cagr", "sharpe", "max_drawdown", "ann_turnover"):
        assert key in m
    assert len(res.equity) == len(res.weights)
    assert res.equity.notna().all()


def test_weights_respect_gross_cap(btc, eth):
    res = run_backtest({"BTCUSDT": btc, "ETHUSDT": eth}, DEFAULT, lookback=100)
    gross = res.weights.sum(axis=1)
    assert (gross <= DEFAULT.risk.max_gross + 1e-9).all()
    assert (res.weights.max(axis=None) <= DEFAULT.risk.max_asset_weight + 1e-9)


def test_circuit_breaker_limits_drawdown(btc, eth):
    res = run_backtest({"BTCUSDT": btc, "ETHUSDT": eth}, DEFAULT, lookback=100)
    # Sized at ~12% vol with a flat breaker at -15%, the portfolio drawdown
    # must stay far above the raw asset drawdowns (which exceed -50%).
    assert res.metrics["max_drawdown"] > -0.30


def test_higher_costs_strictly_reduce_returns(btc, eth):
    cheap = SystemConfig(costs=CostConfig(fee_bps_per_side=0, slippage_bps_per_side=0))
    dear = SystemConfig(costs=CostConfig(fee_bps_per_side=50, slippage_bps_per_side=50))
    ohlc = {"BTCUSDT": btc, "ETHUSDT": eth}
    r_cheap = run_backtest(ohlc, cheap, lookback=100)
    r_dear = run_backtest(ohlc, dear, lookback=100)
    assert r_cheap.metrics["total_return"] > r_dear.metrics["total_return"]


def test_no_lookahead_under_truncation(btc, eth):
    """Equity through day t must be identical whether or not future data
    exists in the input — the strictest practical lookahead test."""
    ohlc_full = {"BTCUSDT": btc, "ETHUSDT": eth}
    cut = len(btc) - 200
    ohlc_cut = {s: df.iloc[:cut] for s, df in ohlc_full.items()}
    eq_full = run_backtest(ohlc_full, DEFAULT, lookback=100).equity.iloc[:cut]
    eq_cut = run_backtest(ohlc_cut, DEFAULT, lookback=100).equity
    assert np.allclose(eq_full.values, eq_cut.values)


def test_grid_runs_all_lookbacks(btc, eth):
    grid = run_grid({"BTCUSDT": btc, "ETHUSDT": eth}, DEFAULT)
    assert list(grid.index) == list(DEFAULT.trend.lookbacks)


def test_walk_forward_covers_history(btc, eth):
    wf = walk_forward({"BTCUSDT": btc, "ETHUSDT": eth}, DEFAULT, lookback=100)
    assert len(wf) >= 2
    assert {"total_return", "sharpe", "max_drawdown"} <= set(wf.columns)
