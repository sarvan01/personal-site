# Two-Sleeve Trading System (MVP)

Implementation of the system designed in
[`docs/trading-system-analysis.md`](../docs/trading-system-analysis.md)
(sections 5, 7, and 8). This is the **week 1–3 MVP**: data pipeline,
risk engine, backtest harness, regime engine, trend + carry signals, and a
one-page status dashboard.

**This system places no live orders.** That is deliberate. Per the
pre-registered validation protocol, live capital comes only after the real-data
backtest passes, four clean weeks of paper trading, and reconciliation of
assumed vs. observed costs.

## What is implemented

| Module                        | Report section | What it does                                                                          |
| ----------------------------- | -------------- | ------------------------------------------------------------------------------------- |
| `trading_system/risk.py`      | §5 Risk engine | Vol-target sizing, 0.5% per-trade risk-to-stop, 25% asset cap, gross cap, −10%/−15% drawdown circuit breakers |
| `trading_system/strategy.py`  | §5 Sleeve A    | Long/flat Donchian trend signal on liquid majors, ATR stop distances                  |
| `trading_system/carry.py`     | §5 Sleeve B    | Funding-rate carry signal with 10%/5% hysteresis hurdles, sleeve backtest             |
| `trading_system/regime.py`    | §7 Regime      | Trend + stress axes → 4 states → exposure multiplier                                  |
| `trading_system/backtest.py`  | §5 Validation  | Daily-bar backtest, one-bar execution lag, 25 bps/side pessimistic costs, lookback grid, walk-forward |
| `trading_system/data.py`      | §7 Data        | Binance klines + funding fetcher with CSV cache; synthetic generator for offline work |
| `trading_system/report.py`    | §7 Dashboard   | `out/status.json` + one-page `out/status.html` (the Home screen)                      |

## Quickstart

```bash
cd trading-system
pip install -r requirements.txt

# 1. Verify the machinery (no network needed)
python -m pytest tests/ -q

# 2. Offline end-to-end demo on synthetic data
python scripts/run_backtest.py --synthetic
python scripts/daily_signals.py --synthetic   # writes out/status.html

# 3. The real thing (requires network access to Binance)
python scripts/fetch_data.py                  # caches data/ CSVs
python scripts/run_backtest.py                # the pre-registered grid test
python scripts/daily_signals.py               # daily cron candidate
```

## The pre-registered pass criterion

`run_backtest.py` prints PASS/FAIL against the criterion fixed in the report
**before** any results were seen: positive net return, Sharpe > 0.7, and max
drawdown < 35% across **every** lookback in the grid (50/100/200). If real
data fails this, the strategy is not traded — the criterion does not move.

Note: the `--synthetic` run is expected to FAIL the criterion. Synthetic data
exists to validate the pipeline (no lookahead, costs charged, breakers fire),
not to audition the strategy.

## Configuration

All parameters live in `trading_system/config.py` and mirror the report.
Changing a parameter after seeing results is curve-fitting; if you change
one, log why in a hypothesis log entry first.

## What is intentionally absent

- **Order execution** — comes after validation, paper-first, behind the risk
  engine's pre-trade checks.
- **Sentiment/NLP, on-chain feeds, narrative baskets** — phase 2+ research
  questions, each requiring its own hypothesis-log entry and test.
- **Alt universe beyond BTC/ETH** — expand only with a point-in-time liquidity
  screen to avoid survivorship bias.

## Disclaimers

Educational/research tooling for the account owner. Not financial advice.
Crypto strategies routinely draw down 20–30%; size so that survival never
depends on a backtest being right.
