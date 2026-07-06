# Auto-Trading Readiness — Audit & Battle-Test Record

Dated 2026-07-02. A deep audit of the money path (sizing → paper → execution)
before any automated trading, with each finding proven by a failing test
before its fix. The Milk Road context-feed work is parked: it is display-only
and adds no edge; hardening the validated system took priority.

## Audit findings

| #   | Severity | Finding                                                                                                                                                                                              | Status                                                                                            |
| --- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| F1  | Critical | **Gross-cap divergence.** Backtest scaled portfolio gross to 100%; `latest_targets` (dashboard/paper/executor input) never applied that cap; the executor hard-rejected over-cap sets. On the system's highest-conviction days: backtest ≈100% gross, paper held >100%, live would have refused to trade entirely. | **Fixed.** Shared `risk.cap_gross()` applied identically in all three paths; executor scales, never refuses. Proven by `tests/test_audit_findings.py`. |
| F2  | High     | **Daily replay crashed on ragged data.** One missing bar for one symbol (exchange outage, later listing) raised `KeyError` and killed the daily run.                                                    | **Fixed.** Replay moved into `signals.replay_targets()` with calendar alignment + forward-fill; symbols with no data yet are skipped, not fatal.        |
| F3  | High     | **Live orders ignored exchange filters.** Sell quantities were rounded to 5 decimals regardless of the symbol's `LOT_SIZE` step (XRP steps in whole units) and `NOTIONAL` minimum — testnet/live orders would be rejected or mis-sized. | **Fixed.** Per-symbol filters fetched from `exchangeInfo` (cached, graceful fallback), quantities floor-quantized, sub-minimum orders skipped **without** aborting the rest of the rebalance. |
| F8  | Medium   | **Go/no-go memo overclaimed.** It said live required four conditions but only checked two, and had no notion of the testnet stage.                                                                       | **Fixed.** `decision_stage()` enforces PAPER → TESTNET → LIVE; live unlocks only after testnet fills show costs within 1.5× of assumptions.            |
| F5  | Low      | Dashboard "target weight" shows pre-breaker targets while the paper account applies the breaker.                                                                                                       | Accepted; breaker state is shown separately in the risk panel.                                     |
| F6  | Open     | **Carry sleeve is monitored but not paper-traded.** The paper clock validates Sleeve A (trend) only.                                                                                                    | Documented gate: carry goes live only after its own paper period, or starts at token size with manual review. |
| F7  | Low      | `days_to_replay` falls back to stepping 1 day if the ledger's last date is missing from a re-fetched index.                                                                                             | Accepted; logged behavior.                                                                         |
| F9  | Open     | **Delisting/universe change is manual.** A symbol that stops trading forward-fills a frozen price; there is no automated forced exit.                                                                   | Documented: universe changes are a human decision with a hypothesis-log entry.                     |

## Battle-test battery (`scripts/stress_test.py`)

Run it on real data (`python scripts/stress_test.py`) after any material
change and before going live. It writes `out/stress_report.json`, which the
cockpit and Next.js dashboard display automatically:

- **Flash crash**: −40% single day across every symbol. Portfolio loss is
  bounded by gross exposure going in (vol targeting keeps this small), and
  the −15% breaker flattens the book on the next bar.
- **Worst historical year**: the worst rolling ~1y window in the sample —
  the pain you must expect to repeat.
- **Ragged data**: random missing bars must not break the pipeline.
- **Monte Carlo**: block-bootstrap of the backtest's own daily returns →
  1y-forward return percentiles and breaker-hit probabilities. Caveat: a
  bootstrap cannot produce a regime worse than its worst sampled block —
  treat tails as optimistic.

## The staged path to automated trading

1. **PAPER** — ≥20 clean days via the daily run (`daily.bat`). No config
   changes; overrides reset the clock.
2. **TESTNET** — schedule `scripts/execute.py --venue testnet --execute`
   after the daily cockpit run; testnet fills populate observed costs in the
   reconciliation.
3. **LIVE at 10% size** — unlocks only when the memo shows observed costs
   within 1.5× of assumptions. Scale per `RISK_POLICY.md` (10% → 50% → 100%),
   only while reconciliation stays clean.

The cockpit's decision memo (`out/decision_memo.md`) and the dashboard's
stage pipeline show exactly which stage you are in and what blocks the next.

## What automation means here (and what it doesn't)

Automation = the *scheduled* daily chain `fetch → cockpit → execute`, every
order passing the same risk checks (per-asset cap, gross cap, circuit
breaker) as the backtest. It does **not** mean the dashboard places orders
(it is read-only by design), and it does not mean unattended forever: the
weekly 30-minute review ritual from `RISK_POLICY.md` remains mandatory.
