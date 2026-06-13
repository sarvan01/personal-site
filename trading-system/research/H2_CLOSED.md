# H2 — Railgun / privacy hypothesis: CLOSED (rejected)

**Status:** rejected across all three pre-registered tests (2026-06-13). No
capital, ever, on this thesis. This file is the archive marker; the code below
is kept as a reproducible audit trail, **not** as part of the trading path.

## Claim

"Privacy-focused assets (XMR, ZEC, SCRT, RAIL, DASH) outperform during
periods of uncertainty." (The observation that originally motivated the
project — see `../../docs/trading-system-analysis.md` §6.)

## Verdict

| Test | "Uncertainty" = | Result | Significance |
| ---- | --------------- | ------ | ------------ |
| U3 event study | privacy-specific events | [0,+5] CAR −1.49% | p=0.761 — no effect |
| U2 crypto-stress regime | BTC top-quintile vol / >20% drawdown | **−0.50%/day** | p=0.995 — rejects |
| U1 macro risk-off | VIX > 25 (CBOE history) | **−0.63%/day** | p=0.996 — rejects |

Privacy coins are high-beta and sell off *harder* in uncertainty — the thesis
is directionally backwards. The original observation was recency bias around
the 2025 ZEC rally. This matches the pre-registered ~55% confounded-artifact
prior.

## Reproduce (optional)

From the `trading-system/` folder:

```bash
python scripts/research/fetch_privacy.py    # needs COINSTATS_API_KEY (or --source coingecko)
python scripts/research/fetch_vix.py        # CBOE VIX history (Stooq/FRED fallback)
python scripts/cockpit.py --config h1b       # renders the U3 + U1/U2 sections when the CSVs exist
```

The cockpit shows the privacy sections **only when** `data/PRIV_*_1d.csv` exist.
Delete those (and `data/VIX_1d.csv`) to keep the daily dashboard focused on the
validated majors system.

## Code kept as the audit trail

- `../trading_system/event_study.py` — U3 beta-adjusted event study + permutation test
- `../trading_system/regime_test.py` — U1/U2 regime difference-in-differences
- `privacy_events.csv` — the pre-registered event list
- `../scripts/research/fetch_privacy.py` — privacy basket fetcher (CoinStats / CoinGecko)
- `../scripts/research/fetch_vix.py` — VIX fetcher (CBOE / Stooq / FRED)

Full record: `hypothesis_log.json` (entry H2).
