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
| `trading_system/macro.py`     | §7 Regime      | Optional macro stress inputs: FRED DXY/real yields, DefiLlama stablecoin flows        |
| `trading_system/event_study.py` | §6 Railgun   | Beta-adjusted event study, permutation test, drop-one robustness, fixed decision rule |
| `trading_system/paper.py`     | §8 Weeks 3–4   | Persistent paper-trading ledger, simulated fills, cost-reconciliation report          |
| `trading_system/cockpit.py`   | §7 Dashboard   | **The cockpit**: one HTML page with everything (see below)                            |
| `trading_system/report.py`    | §7 Dashboard   | Minimal `out/status.json` + `out/status.html` (subset of the cockpit)                 |

Supporting artifacts: `RISK_POLICY.md` (the pre-registered one-page risk
policy), `research/hypothesis_log.json` (every hypothesis: claim → test →
result → decision), `research/privacy_events.csv` (the pre-registered event
list for the Railgun study — extend it **before** looking at returns).

## The cockpit — one command, one page

`scripts/cockpit.py` is the single daily entry point. It runs everything the
available data allows and renders **`out/cockpit.html`** — regime state,
trend signals and target weights, funding-carry status, risk limits,
circuit-breaker state, the paper account with its equity curve, the
backtest-grid PASS/FAIL gate, walk-forward results, the Railgun event-study
verdict, cost reconciliation, the hypothesis log, and a live 30-day-plan
progress checklist. It also writes `out/status.json` (machine-readable) and
`out/decision_memo.md` (the go/no-go memo).

```bash
cd trading-system
pip install -r requirements.txt

# 1. Verify the machinery (no network needed)
python -m pytest tests/ -q

# 2. Offline end-to-end demo on synthetic data
python scripts/cockpit.py --synthetic        # writes out/cockpit.html

# 3. The real thing (requires network access to Binance)
python scripts/fetch_data.py                 # caches data/ CSVs
python scripts/cockpit.py                    # daily cron candidate
```

`scripts/run_backtest.py` and `scripts/daily_signals.py` remain available for
running those pieces individually.

For the Railgun study on real data: place daily close CSVs for the privacy
basket in `data/` named `PRIV_<symbol>_1d.csv` (XMR, ZEC, SCRT, RAIL, DASH —
CoinGecko exports work), review/extend `research/privacy_events.csv` first,
then run `python scripts/cockpit.py`; the study section appears automatically.

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
