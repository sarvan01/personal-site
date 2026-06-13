# Runbook — daily operation

The exact, ordered process. Nothing here places real money until Phase 3,
which is hard-gated.

## Phase 0 — One-time setup

```powershell
cd "<your path>\Trading-system-package\trading-system"
del out\paper_ledger.json          # reset the ledger once, under the h1b config
python scripts/cockpit.py --config h1b   # seeds 60 days, writes out/cockpit.html
start out\cockpit.html             # confirm REAL DATA badge + equity curve
```

## Phase 1 — Daily (≈4 weeks)

**Easiest: double-click `daily.bat`** (it fetches, updates the cockpit, opens it).

Or schedule it once and forget:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\schedule_daily.ps1 -At 02:30
```

(Pick a local time after 01:00 UTC so the daily bar has closed. Remove later
with `... schedule_daily.ps1 -Remove`.)

Or run the two commands by hand:

```powershell
python scripts/fetch_data.py --config h1b
python scripts/cockpit.py   --config h1b
```

Each day adds one real out-of-sample point to the paper account. Running it
twice in a day is harmless (it won't double-count); skipping days is fine
(the next fetch catches up).

## Phase 2 — Decision (after ≈20 trading days)

```powershell
notepad out\decision_memo.md       # flips toward GO when all conditions met
```

GO requires: backtest gate still PASS, ≥20 clean paper days, costs within
bounds, zero manual overrides. NO-GO → keep paper trading or stop. No money
at risk either way.

## Phase 3 — Live, tiny (only after GO)

Order execution is built and risk-checked but **off by default**. Path:

1. **Preview (no orders, no network):**
   ```powershell
   python scripts/execute.py --config h1b
   ```
   Prints exactly what it would trade and simulates fills locally.

2. **Testnet (play money):** get free keys at https://testnet.binance.vision, then
   ```powershell
   setx BINANCE_KEY "your_testnet_key"
   setx BINANCE_SECRET "your_testnet_secret"
   # open a new terminal so the vars load
   python scripts/execute.py --config h1b --venue testnet            # preview
   python scripts/execute.py --config h1b --venue testnet --execute  # send to testnet
   ```

3. **Live (real money) — two independent gates:**
   ```powershell
   setx ALLOW_LIVE_TRADING yes
   python scripts/execute.py --config h1b --venue live --i-understand-live --execute
   ```
   Start at 10% of target size. Every order is checked against the risk
   policy and scaled by the circuit breaker before it is sent.

## Optional — settle the Railgun question (H2)

Independent of the trading clock. Privacy coins aren't reliably on Binance,
so this uses CoinGecko:

```powershell
python scripts/fetch_privacy.py        # XMR/ZEC/SCRT/RAIL/DASH -> data\PRIV_*_1d.csv
python scripts/cockpit.py --config h1b # event-study verdict appears in the cockpit
```

Review `research\privacy_events.csv` first (the pre-registered event list) —
extend it BEFORE looking at returns if you want to. The study beta-adjusts
the basket against BTC (removing the "just high-beta alts" confound), measures
abnormal returns around each event, and runs a permutation test plus a
drop-one-event robustness check. Read the verdict honestly: the prior is ~55%
that it's a confounded artifact.

## The rules (fixed)

- No config changes during the 4 weeks.
- No early go-live on a hot streak.
- Live starts at 10% size; scale only as cost reconciliation stays clean.
- Log every deviation in `research/hypothesis_log.json`.
