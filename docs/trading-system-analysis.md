# Trading System Analysis: An Investment-Committee Review

**Scope of this document.** This is an adversarial review of the proposed "unified trading intelligence terminal," a structured analysis of the Railgun/privacy hypothesis, a ranked survey of alternative strategies, and a concrete recommendation with 30/90-day plans. It is written to maximize probability of success, not excitement. Nothing here is financial advice; it is a research and engineering plan.

**One-paragraph verdict, up front.** The terminal as conceived is a tooling project, not an edge. Aggregating Milk Road, sentiment, on-chain dashboards, and macro data — all of which thousands of other market participants also read — produces zero informational advantage by construction. The highest-probability path is the opposite of the original plan: pick **one** small, testable, capacity-constrained edge (systematic trend-following on liquid crypto majors, plus a delta-neutral funding-carry sleeve), validate it with a rigorous backtest, deploy it tiny, and let the "terminal" emerge later as a thin internal dashboard serving a strategy that already works. The Railgun observation is most likely a beta artifact or a single-regime narrative episode; it deserves a cheap, well-designed test before any capital touches it.

---

## 1. Is the Original Idea Actually Good?

### What is strong about it

- **You can build software.** This is the single most underrated retail advantage. Most retail traders cannot test anything; you can. Every recommendation below leans on this.
- **Two execution venues (Binance + IBKR)** cover crypto spot/perps and equities/ETFs/FX. That is enough surface area for every strategy worth considering at your capital scale.
- **Stated willingness to follow data over emotion.** If genuinely held under drawdown, this is rarer than any data feed.
- **Treating Railgun as a hypothesis rather than a fact** (as the prompt itself demands) is the correct epistemic posture.

### What is weak about it

- **No defined edge anywhere in the plan.** The proposal lists data sources and screens. A data source is not an edge. An edge is a specific, falsifiable claim of the form: "Under condition X, instrument Y exhibits abnormal return Z after costs, because of mechanism M, and the capital that could arbitrage it away doesn't, because of constraint C." The original plan contains zero such claims (the Railgun observation is the closest, and it is untested).
- **Aggregation of public information is not alpha.** Milk Road has hundreds of thousands of readers. Glassnode, Santiment, and the Fear & Greed index are public. Funding rates are printed on every exchange. By the time information is in a newsletter, it is in the price or it is noise. A prettier window onto consensus data is still consensus data.
- **Scope guarantees non-completion.** Eight engines, two broker integrations, five dashboard screens, multi-asset coverage. Solo builders who start with the platform almost never reach the part where a strategy is validated. The platform becomes the product, the procrastination, and the sunk cost.
- **No risk framework.** Position sizing, drawdown limits, and kill criteria are mentioned nowhere in the original concept except as a future "Risk Engine" module. In professional practice this is the first module, not the last.

### What you are missing / blind spots

1. **Costs are the silent killer.** Binance spot fees (~7.5–10 bps with BNB discount), spread, slippage, and funding mean a strategy needs roughly 20–30 bps of gross edge per round trip just to break even. Most sentiment/narrative signals do not clear this bar at retail execution quality.
2. **Capacity and crowding.** Edges that survive for retail are precisely the ones too small for funds to bother with. Designing a "hedge-fund-grade terminal" optimizes for the wrong game; the retail game is finding scraps the whales ignore.
3. **Survivorship and hindsight in narrative investing.** "Privacy assets perform well in uncertainty" is the kind of pattern the brain extracts from one or two vivid episodes (e.g., the late-2025 privacy-coin rally led by ZEC) while forgetting every uncertain period in which privacy coins simply bled with the rest of the long tail.
4. **Behavioral risk dominates model risk at your stage.** The most likely failure mode is not a bad signal; it is overriding the system after three losing trades, or doubling size after three winners.
5. **Regulatory tail risk on the specific thesis asset.** Privacy assets carry delisting risk that most sectors do not: Binance delisted Monero in early 2024, OKX delisted privacy coins, and Railgun itself has faced sanction-adjacent scrutiny (Tornado Cash precedent). An edge you cannot reliably execute or exit is not an edge.

### Assumptions you are implicitly making

- That more data sources → better decisions (false beyond a small number of orthogonal inputs; it mostly adds noise and overfitting surface).
- That sentiment is predictive at the horizon you can trade (extreme sentiment has some contrarian value at multi-week horizons; mid-range sentiment is noise).
- That a tool you build for yourself will discipline you (tools don't create discipline; pre-committed rules and small size do).
- That Binance + IBKR API access is differentiating (it is table stakes).

---

## 2. What Would a Hedge Fund Do Differently?

### Amateur thinking vs. professional thinking in the original plan

| Element of the plan                      | Amateur framing                       | Professional framing                                                                                                        |
| ---------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Unified terminal first                   | "Build the cockpit, then fly"         | Hypothesis → backtest → tiny live deployment → build only the tooling the live strategy demands                              |
| Many data sources                        | More inputs = more edge               | Each input must independently improve out-of-sample performance net of costs, or it is deleted                               |
| Sentiment "engine"                       | Dashboard of feelings                 | One or two quantified series (funding, aggregate OI, basis) with tested predictive value at a defined horizon                |
| Narrative tracking                       | Watch what's hot                      | Cross-sectional relative strength with rebalancing rules, turnover limits, and cost modeling                                 |
| Railgun observation                      | "I noticed a pattern"                 | Pre-registered event study with control baskets and significance tests before a single dollar of exposure                    |
| Risk engine                              | A module to add later                 | The first thing built; sizing and kill criteria defined before the first trade                                               |
| Execution on two venues                  | Integration breadth                   | Execution quality measurement: slippage per trade logged and reconciled against the backtest's cost assumptions              |

### Which proposed features create actual edge vs. only complexity

**Could contribute to edge (keep, in reduced form):**

- Funding rates and open interest (these are positioning data, the closest thing to non-consensus information in your stack).
- Relative-strength measurement across sectors/baskets (a real, testable cross-sectional signal).
- Automated execution with logging (reduces behavioral error — a genuine, underrated edge for retail).
- A regime filter built from a *small* number of measurable inputs.

**Creates complexity, not edge (cut or defer):**

- Milk Road ingestion/NLP (use it as discretionary context over coffee; do not pipe it into a signal).
- Twitter/Reddit scraping and sentiment NLP (high engineering cost, weak and decaying signal, severe overfitting risk).
- General on-chain analytics (most metrics are repackagings of price/volume; a few, like stablecoin net flows, are worth a later look).
- Multi-screen dashboard suite (build one page, after the strategy exists).
- Stock + macro + crypto coverage at launch (one asset class until profitable).

A hedge fund's deepest difference is **process**: explicit hypotheses, point-in-time data, out-of-sample discipline, cost modeling, capacity analysis, pre-committed kill criteria, and post-trade attribution. Every one of those is replicable by a solo builder. The data moats are not — so don't compete on data.

---

## 3. Twenty-Two Alternative Strategies, Assessed

For each: expected edge, difficulty, data needs, sustainability, key risk. "Edge" here means realistic net-of-cost expectancy for a solo retail-scale operator, not what a fund could extract.

1. **Time-series trend-following on BTC/ETH (+ a few liquid majors).** Edge: moderate and well documented (time-series momentum is among the most robust anomalies across all asset classes; crypto's retail-driven herding makes it stronger there). Difficulty: low. Data: daily OHLCV. Sustainability: high — it has survived decades of publication because it requires sitting through long flat/whipsaw periods, which most capital won't do. Risk: regime of prolonged chop; 2021-style sudden reversals; drawdowns of 20–30% are normal for the strategy class.
2. **Cross-sectional momentum across top ~30 liquid alts.** Edge: moderate (documented in crypto academic literature, e.g., Liu–Tsyvinski-style factor work). Difficulty: low–medium. Data: daily OHLCV, liquidity filters. Sustainability: medium-high. Risk: alt liquidity evaporates in risk-off; high turnover costs; delistings.
3. **Perp funding-rate carry (delta-neutral cash-and-carry).** Edge: moderate, structural — longs pay shorts in bull regimes because retail demands leverage; you collect by holding spot and shorting the perp. Historically mid-single-digit to >20% annualized in hot regimes. Difficulty: medium (margin management, basis tracking). Data: funding history, spot+perp prices. Sustainability: medium-high (structural retail leverage demand keeps regenerating it). Risk: exchange/counterparty risk (the FTX lesson), funding flips negative, liquidation mechanics during gaps.
4. **Futures basis trade (quarterly futures vs. spot).** Edge: similar to #3, lumpier. Difficulty: medium. Sustainability: medium. Risk: same counterparty/basis-blowout risks; capacity fine at your scale.
5. **Volatility risk premium (selling options, e.g., covered calls on BTC via Deribit or ETF options via IBKR).** Edge: moderate, structural. Difficulty: medium-high. Data: options chains, IV history. Sustainability: high. Risk: short-vol tail risk; one crash can erase years; requires strict sizing — not a beginner sleeve.
6. **Narrative/sector rotation (AI, DePIN, RWA, privacy, gaming baskets via relative strength).** Edge: low-moderate, and only when implemented as *measured relative strength with rules*, not vibes. Difficulty: medium. Data: basket construction, daily prices. Sustainability: low-medium — narrative half-lives are shortening. Risk: buying tops of attention cycles; basket survivorship bias in backtests.
7. **Sentiment-extreme contrarian model (Fear & Greed, funding extremes, social volume spikes).** Edge: low-moderate at multi-week horizons, only at extremes. Difficulty: medium. Sustainability: medium. Risk: extremes get more extreme; signal is infrequent (small sample).
8. **Sentiment divergence (price up, sentiment down, etc.).** Edge: unproven; mostly research-paper material that fails after costs. Difficulty: high (NLP pipeline). Sustainability: low. Risk: overfitting; decaying APIs (Twitter data access cost). **Reject as a core.**
9. **On-chain accumulation models (exchange outflows, dormancy, HODL waves).** Edge: low — most metrics are slow, repackaged price/volume; widely watched via Glassnode. Difficulty: medium. Sustainability: low-medium. Risk: metric redefinition, exchange wallet mislabeling. Defer.
10. **Stablecoin flow / aggregate stablecoin market-cap as a liquidity signal.** Edge: low-moderate as a *regime input*, not a standalone strategy. Difficulty: low. Data: free (DefiLlama, CoinGecko). Sustainability: medium. Risk: structural breaks (regulation of issuers).
11. **Smart-money wallet tracking (Nansen-style, copy whales).** Edge: low and decaying — labeled wallets are watched by thousands of bots that front-run you; truly smart wallets rotate addresses. Difficulty: high. Sustainability: low. **Reject.**
12. **Event-driven: exchange listing announcements.** Edge: real historically (listing pops) but mostly captured in the first seconds by bots; retail gets the post-pop fade. Difficulty: high (speed game). Sustainability: low at retail latency. **Reject.**
13. **Event-driven: token unlock calendar (short/avoid into large unlocks).** Edge: low-moderate, documented pre-unlock underperformance; usable mainly as a *filter* (don't be long into a >5% supply unlock). Difficulty: low. Data: TokenUnlocks-style calendars. Sustainability: medium (increasingly priced, but laziness persists). Risk: shorting alts is expensive and squeeze-prone — use as an avoidance filter, not a short book.
14. **Macro liquidity overlay (Fed net liquidity, global M2, DXY, real yields → crypto beta on/off).** Edge: low-moderate as a *filter* on strategy #1; weak as a standalone timing signal (few independent observations per decade). Difficulty: low-medium. Data: FRED, free. Sustainability: medium. Risk: regime relationships are unstable and the sample of macro cycles is tiny.
15. **Equity sector rotation / dual momentum on ETFs via IBKR.** Edge: low-moderate, well documented (Antonacci-style dual momentum), modest Sharpe, very low maintenance. Difficulty: low. Sustainability: high. Risk: crowded; decade-long stretches of underperformance vs. buy-and-hold. Good as a boring second engine for non-crypto capital.
16. **Mean reversion on BTC/ETH at short horizons (1–3 day oversold bounces).** Edge: low and regime-dependent; crypto majors trend more than they revert at daily horizons. Difficulty: medium. Sustainability: low-medium. Risk: catching knives in trend regimes. Defer.
17. **Cross-exchange arbitrage / triangular arb.** Edge: ~zero for a solo operator in 2026; HFT firms own this. **Reject.**
18. **Market-making / grid bots.** Edge: negative expectancy for retail in trending markets (inventory risk); profitable MM requires queue position and rebates you don't have. **Reject.**
19. **MEV / on-chain searcher strategies.** Edge: real but an arms race against specialized teams; also ethically/legally murky in places. **Reject.**
20. **Airdrop / points farming.** Edge: real, *not a trading edge* — it's paid labor with capital at risk in smart contracts. Returns have compressed since 2021–2023. Difficulty: medium. Sustainability: low (each cycle gets more sybil-resistant and crowded). Optional side income, not the core.
21. **AI research assistant (LLM pipeline over Milk Road, filings, news).** Edge: zero direct alpha — it's a productivity tool. Value: saves hours, surfaces candidates for *human* judgment. Worth building cheaply *for yourself* in week 2, not as the product.
22. **The terminal as a business (sell the dashboard/newsletter, not the trades).** Edge: not a trading edge at all, but the **highest expected dollar value** item on this list for someone with your skills: tooling + content for crypto traders monetizes attention, and your P&L doesn't depend on beating markets. Difficulty: medium-high (distribution is the hard part, not code). Sustainability: medium-high. Risk: crowded creator market; conflicts with actually trading well.

---

## 4. Ranking

Scores are 1–10. **Score = (2 × Edge + Sustainability + (10 − Difficulty) + (10 − Cost)) / 5**, i.e., edge double-weighted, cheap-and-easy rewarded. "Cost" includes data, infrastructure, and capital lockup.

| #   | Idea                                       | Edge | Difficulty | Cost | Sustainability | Score   | Verdict           |
| --- | ------------------------------------------ | ---- | ---------- | ---- | -------------- | ------- | ----------------- |
| 1   | Trend-following BTC/ETH majors             | 6    | 2          | 1    | 8              | **7.4** | **Core**          |
| 3   | Funding-rate carry (delta-neutral)         | 6    | 4          | 3    | 7              | **6.4** | **Core sleeve 2** |
| 15  | ETF dual momentum (IBKR)                   | 4    | 2          | 1    | 8              | 6.3     | Passive engine    |
| 2   | Cross-sectional alt momentum               | 5    | 4          | 2    | 6              | 6.0     | Phase 2 extension |
| 13  | Unlock-calendar avoidance filter           | 4    | 2          | 2    | 6              | 6.0     | Cheap filter      |
| 22  | Terminal as a business (sell tools)        | 5\*  | 6          | 4    | 7              | 5.4     | Separate decision |
| 4   | Quarterly basis trade                      | 5    | 4          | 4    | 6              | 5.6     | Variant of #3     |
| 14  | Macro liquidity regime filter              | 3    | 3          | 1    | 6              | 5.6     | Filter only       |
| 10  | Stablecoin-flow regime input               | 3    | 2          | 1    | 5              | 5.6     | Filter only       |
| 5   | Volatility risk premium                    | 6    | 7          | 5    | 8              | 5.6     | Year-2 candidate  |
| 7   | Sentiment-extreme contrarian               | 3    | 4          | 3    | 5              | 4.8     | Filter at best    |
| 6   | Narrative/sector rotation baskets          | 3    | 5          | 3    | 4              | 4.2     | Phase 3 research  |
| 20  | Airdrop/points farming                     | 4    | 5          | 5    | 3              | 4.2     | Side income only  |
| 16  | Short-horizon mean reversion               | 3    | 5          | 3    | 4              | 4.2     | Defer             |
| 9   | On-chain accumulation models               | 2    | 5          | 4    | 4              | 3.8     | Defer             |
| 21  | AI research assistant                      | 0\*  | 3          | 2    | 6              | 3.8     | Tool, not edge    |
| 8   | Sentiment divergence NLP                   | 2    | 7          | 6    | 3              | 2.8     | Reject            |
| 11  | Smart-money wallet copying                 | 2    | 7          | 5    | 2              | 2.6     | Reject            |
| 12  | Listing-event sniping                      | 3    | 8          | 6    | 2              | 2.4     | Reject            |
| 19  | MEV                                        | 4    | 9          | 7    | 4              | 2.4     | Reject            |
| 17  | Cross-exchange arbitrage                   | 1    | 8          | 7    | 2              | 1.4     | Reject            |
| 18  | Retail market-making / grid bots           | 1    | 7          | 5    | 2              | 1.8     | Reject            |
| —   | **Original idea: all-in-one terminal**     | 1    | 9          | 7    | 5              | 1.6     | **Replace**       |

\*#22's "edge" is business value, not market alpha; #21's value is time saved. The original idea scores near the bottom **as a trading system** because it has the highest difficulty and cost attached to the least-defined edge.

---

## 5. The Recommended System (Replacing the Original Idea)

### "Two Sleeves and a Filter"

**Sleeve A — Directional: regime-filtered trend-following.**

- Universe: BTC, ETH, and at most 3–5 additional majors passing a strict liquidity screen (e.g., >$100M reliable daily volume on Binance spot).
- Signal (starting point, to be validated, not optimized): long when price > 100-day high-watermark style channel or 50d/200d alignment with positive 90-day return; flat (in stablecoin/T-bills) otherwise. Long/flat only — no shorting alts.
- Regime filter: reduce gross exposure when (a) BTC 30-day realized vol is in its top decile, or (b) the macro-liquidity composite (DXY trend, real yields, stablecoin aggregate market-cap trend) is risk-off. The filter scales size; it does not generate trades.
- Sizing: volatility targeting. Each position sized so the portfolio targets ~10–12% annualized vol initially; per-trade risk to stop ≤ 0.5% of equity.

**Sleeve B — Market-neutral: funding-rate carry.**

- Hold spot BTC/ETH, short the equivalent perp on Binance, collect funding when the trailing 7-day average funding exceeds a hurdle (e.g., >10% annualized) — exit to flat when it decays below ~5% or flips negative.
- Hard cap: ≤ 30% of account in this sleeve; conservative margin (≥3× maintenance buffer) so a 20% gap cannot liquidate the short leg.
- This sleeve pays you to wait during the very euphoric regimes where Sleeve A is most exposed — the two are naturally complementary.

**Risk engine (built first, non-negotiable):**

- Per-position risk ≤ 0.5% of equity to stop; max single-asset exposure 25%; max gross 100% (no leverage on the directional sleeve).
- Portfolio circuit breaker: at −10% peak-to-trough equity drawdown, halve all sizes; at −15%, go flat and conduct a written post-mortem before resuming.
- Kill criteria pre-registered per strategy: e.g., "If 12-month live Sharpe is negative AND live slippage exceeds backtest assumptions by >50%, retire the strategy." Written down before the first trade.

**IBKR's role:** hold non-deployed capital in T-bill ETFs/money market; optionally run the boring ETF dual-momentum engine (#15) on equity capital. It also diversifies venue risk away from Binance.

### Why it is superior to the terminal

It is one falsifiable strategy with one risk framework, buildable by one person in 30 days, testable on free data, and its failure modes are known and survivable. The terminal is fifty integrations in search of a hypothesis.

### Why it should work

- Time-series momentum is the most replicated anomaly in empirical finance, and crypto — retail-dominated, leverage-driven, narrative-prone — exhibits it strongly. The behavioral mechanism (herding, anchoring, slow diffusion of information, forced liquidation cascades) regenerates it.
- Funding carry exists because retail persistently pays for leveraged long exposure; that demand is structural to crypto market design.
- Both edges persist *because* they are uncomfortable: trend-following loses small amounts most of the time, and carry requires patience and operational care. Discomfort is the moat.

### Why it might fail

- A multi-year choppy, range-bound regime grinds the trend sleeve down (this is the base-case bad outcome — expect it some years).
- Crowding compresses funding rates structurally as more basis-trade capital (including ETF-related arbitrage) enters.
- Counterparty event on Binance impairs the carry sleeve mid-trade.
- The operator (you) overrides the system after a normal 15% drawdown — historically the #1 cause of death for systems like this.
- Backtest overfitting: if you tune parameters until the equity curve is pretty, the live version will not match. Mitigation below.

### How to validate it

1. Backtest 2017→present on daily data with **costs modeled pessimistically** (15 bps per side + slippage), including delisted coins in any alt universe (point-in-time universe to kill survivorship bias).
2. **No parameter optimization.** Test a small pre-declared grid (e.g., 50/100/200-day lookbacks); require the strategy to be profitable across *all* of them, not at the best one. Robustness, not peak performance.
3. Walk-forward check: does each 2-year out-of-sample window stay above zero net?
4. Paper trade 4 weeks; reconcile every fill against backtest cost assumptions.
5. Go live at 10% of intended size for 3 months before scaling.

---

## 6. The Railgun / Privacy Hypothesis

**Claim under test:** "Privacy-focused assets outperform during periods of uncertainty."

### Why skepticism is the correct prior

1. **The claim is doubly vague** — "privacy assets" (which? XMR, ZEC, RAIL, SCRT behave very differently) and "uncertainty" (macro risk-off? crypto drawdowns? regulatory events?) are both undefined. Vague hypotheses are unfalsifiable and therefore always feel true.
2. **Recency/hindsight risk:** the most vivid recent datapoint is the late-2025 privacy rally (ZEC's enormous run, with sympathy moves across the privacy basket). One spectacular episode creates exactly this kind of belief. One episode is one observation.
3. **Beta confound:** privacy coins are small-cap, high-beta assets. In genuine risk-off they should *underperform* the majors. If they appear to outperform "during uncertainty," either (a) "uncertainty" is being defined after the fact around episodes where they happened to rally, or (b) the effect is real but driven by a *specific* event type (privacy-relevant catalysts), not uncertainty generally.
4. **Tradability problems even if true:** RAIL specifically is thin (mostly DEX liquidity, no major CEX perp), and the whole sector carries delisting risk (Binance delisted XMR in Feb 2024; multiple exchanges have purged privacy coins). Wide spreads and venue risk can consume a real but modest edge entirely.

### Research methodology (pre-registered, then executed — in that order)

**Step 1 — Define the basket and controls (point-in-time).**

- Privacy basket: XMR, ZEC, SCRT, RAIL, DASH (include dead/delisted members as of each historical date — survivorship control).
- Control basket A: market (BTC, and a broad top-50 index).
- Control basket B: beta/size-matched non-privacy alts — for each privacy coin, 3–5 alts matched on trailing 90-day beta to BTC and market-cap decile. This is the critical control: it isolates "privacy" from "small high-beta alt."

**Step 2 — Define "uncertainty" three separate ways, in advance:**

- **U1 Macro risk-off:** VIX > 25 (or top-quintile MOVE), measured on the prior day's close.
- **U2 Crypto stress:** BTC 30-day realized vol top quintile, or BTC drawdown > 20% from 90-day high.
- **U3 Privacy-relevant events (event study):** a hand-collected, dated list — Tornado Cash sanctions (Aug 2022), major exchange privacy-coin delistings, CBDC/surveillance policy announcements, Samourai/mixer prosecutions, EU AML privacy provisions, etc. Collect the event list *before* looking at returns.

**Step 3 — Tests.**

- Regime test (U1, U2): mean daily excess return of privacy basket vs. control B within regime vs. outside regime; difference-in-differences.
- Event study (U3): cumulative abnormal returns (CAR) over windows of [−5, 0], [0, +5], [0, +20] days around each event, abnormal = privacy return − beta-matched control return.
- Significance: because crypto returns are fat-tailed and volatility-clustered, use **block bootstrap / permutation tests** (shuffle event dates 10,000 times, compare observed CAR to the permuted distribution), not plain t-tests.
- Robustness: split 2019–2022 vs. 2023–present; drop ZEC's 2025 episode and re-run (does the entire result depend on one rally?); per-coin breakdown (is it "privacy" or just "XMR"?).
- Economic test: re-run with realistic costs for the *tradable* implementation (which probably means XMR/ZEC on the venues that still list them — possibly not RAIL at all).

**Step 4 — Decision rule, written before running anything:** trade it only if the effect survives the beta-matched control, the bootstrap p < 0.05, the drop-one-episode test, and costs — and even then, cap it at ≤ 5% of capital as a satellite, given delisting risk.

### Probability estimates (reasoned, not guessed)

- **Genuine, durable, tradable edge ("privacy outperforms in uncertainty, generally"): ~10%.** The mechanism story (uncertainty → demand for financial privacy → token buying) is plausible for *usage* but weak for *tokens* — token prices are dominated by speculative flows, and the general claim has too many ways to be a mirage. Most published crypto cross-sectional effects die under beta-matched controls.
- **Randomness / confounded artifact (beta, survivorship, hindsight around one rally): ~55%.** This is the base rate for visually-noticed patterns in small, volatile baskets.
- **Real but regime/event-dependent: ~35%.** The most plausible surviving version: privacy assets respond positively to *privacy-specific regulatory/surveillance catalysts* (an event-driven narrative effect), not to "uncertainty" broadly. This would make it an occasional event trade with a deteriorating venue problem — worth knowing, not worth building a system around.

(The three sum to 100% as mutually exclusive top-level outcomes; the test above is cheap — roughly a weekend of work — and resolves which world you're in. That is the correct price for this hypothesis: one weekend, zero dollars.)

---

## 7. The Trading Intelligence Platform — Right-Sized

The platform you asked for, redesigned so each module is small, measurable, and built **in the order the strategy needs it**, not all at once.

### Market Regime Engine (build week 1 — it's ~5 indicators, not 8 moods)

Replace the eight fuzzy labels (bull/bear/panic/euphoria/...) with a 2-axis score, because every label you listed is a combination of these two measurable axes:

- **Trend axis:** BTC price vs. 200-day MA, 90-day return sign, % of top-20 alts above their 100-day MA (breadth).
- **Stress/liquidity axis:** BTC 30-day realized vol percentile, aggregate stablecoin market-cap 30-day change, DXY 60-day trend, perp aggregate funding level.

Output: one of four states — *Risk-On Trending, Risk-On Euphoric (trend + top-decile funding/vol), Chop, Risk-Off* — each mapped to a gross-exposure multiplier (e.g., 1.0 / 0.6 / 0.5 / 0.25). Euphoria isn't a feeling; it's funding + vol percentiles.

### Sentiment Engine (build week 3 — quantified inputs only)

- Funding rates (per-asset and aggregate), open interest change, perp-spot basis — from Binance, free.
- Fear & Greed index as a single extreme-flag (signal only at <15 or >85).
- Milk Road, news, X, Reddit: consumed by the human as context, **not** piped into signals. Revisit NLP only after 6 months of live profitability, and only as a researched hypothesis like any other.

### Narrative Engine (build month 2–3, as research not signals)

- Maintain static baskets (AI, privacy, DePIN, RWA, gaming, infra, L1, L2, meme) of 5–10 liquid names each.
- Compute 30/90-day relative strength vs. BTC, breadth within basket, and turnover-adjusted momentum rank. Render as a weekly-updated table. This is the *only* part of the original "narrative" vision that is measurable.

### Opportunity Engine (month 3+)

A daily ranked shortlist, max 10 rows: trend-signal candidates from Sleeve A's universe, funding-carry opportunities above hurdle, basket relative-strength leaders, and unlock-calendar warnings (filter #13). Each row links to the evidence. No black-box "scores."

### Risk Engine (build first, week 1, before any signal code)

Exactly as specified in §5: vol targeting, 0.5% per-trade risk, 25% single-asset cap, −10%/−15% drawdown circuit breakers, pre-registered kill criteria, and a position ledger that is the single source of truth.

### Execution Layer (weeks 2–4)

- Binance: REST/WebSocket client, idempotent order placement, limit-order-first policy, fill logging with realized slippage vs. mid at signal time.
- IBKR: via `ib_insync`-style API for the ETF engine and cash management. Paper-trading endpoints first on both. Every order routed through the risk engine's pre-trade checks — no manual orders outside the system.

### Dashboard (one page in month 1; five screens only if they earn their place)

1. **Home:** regime state, equity curve, current drawdown vs. circuit-breaker levels, open positions with stops, today's signals. (This is the MVP dashboard — everything else is later.)
2. **Research:** backtest results browser, hypothesis log (every idea gets a written entry: claim, test, result, decision).
3. **Opportunity:** the ranked shortlist above.
4. **Execution:** order ticket with pre-trade risk check, fill history, slippage stats.
5. **Portfolio:** exposure by asset/sleeve/venue, funding P&L attribution, performance vs. BTC benchmark.

Build order: Risk → data pipeline → backtester → Home screen → execution → the rest. If the strategy isn't profitable, screens 2–5 are never built, and that's the system working as intended.

---

## 8. The Most Important Question: What I Would Build

Starting with Milk Road Premium, Binance, IBKR, and software skill, compensated purely on your risk-adjusted outcome, I would build **the two-sleeve system of §5, preceded by a backtest, wrapped in the §7 risk engine, with a one-page dashboard** — and I would treat Milk Road as breakfast reading, not infrastructure.

**Why:** it is the only option on the ranked list that combines a documented, mechanism-backed edge with low build cost, free data, retail-appropriate capacity, and survivable failure modes. Everything else is either a filter, a phase-2 extension, a rejected idea, or a different business.

- **First MVP:** a Python backtester (daily bars, pessimistic costs, point-in-time universe) + the risk engine + a single static HTML/Next.js status page. No live orders.
- **First test:** the pre-declared trend-parameter grid on BTC/ETH 2017–present, walk-forward, net of 15 bps/side. Pass = positive net return and Sharpe > 0.7 across the whole grid, max drawdown < 35%. (Run the Railgun event study the same week — it's a weekend — and archive the result either way.)
- **First trade:** a paper trade. The first *real* trade, after 4 clean paper weeks: one BTC position on a fresh trend signal, sized to risk 0.5% of account equity to its ATR-based stop, entered with a limit order, logged automatically. Boring by design. The first trade's job is to test the *pipeline*, not to make money.

### 30-Day MVP Plan

- **Week 1:** Risk engine spec written and coded (sizing, caps, circuit breakers, kill criteria — as code and as a one-page written policy). Data pipeline: Binance daily klines + funding history into SQLite/Parquet; FRED series (DXY, yields) ingested.
- **Week 2:** Backtest harness (costs, point-in-time universe, walk-forward). Run the trend grid on BTC/ETH. Run the Railgun event study (§6) over the weekend. Write up both results in the hypothesis log.
- **Week 3:** If backtest passes: signal generator running daily as a cron job, regime engine v1 (the 5 indicators), one-page dashboard showing regime/signals/risk state. Paper-trading wiring to Binance testnet.
- **Week 4:** Paper trading live daily. Funding-carry monitor built (alert when 7-day funding > hurdle). Reconciliation report: paper fills vs. backtest assumptions. Decision memo: go/no-go for live capital.

### 90-Day Plan

- **Month 2:** Go live at 10% of intended size, trend sleeve only. Add the carry sleeve in paper mode; verify margin/liquidation math under simulated 20% gaps. Add unlock-calendar filter. Weekly 30-minute review ritual: every trade vs. system, every override (target: zero) logged.
- **Month 3:** If live slippage and behavior match backtest (within 50% on costs, zero overrides): scale trend sleeve to 50% of target size; take carry sleeve live small (≤10% of account). Stand up ETF dual-momentum on IBKR for idle capital. First quarterly report: live vs. backtest attribution, kill-criteria check, decide the *one* research question for the next quarter (candidates: cross-sectional alt momentum, or the privacy event-trade if the study surprised us).
- **Throughout:** no new data sources, no new screens, no Twitter NLP. The discipline *is* the system.

---

## Final Deliverables

1. **Single best business/trading idea:** *as a trading system* — the two-sleeve trend + funding-carry system (§5). *As a business* — if you ever want one, the dashboard sold to other traders (#22) beats trading it yourself in expected dollars, but it is a different venture with different success criteria; don't conflate them. Pick the trading system first; it makes the eventual product honest ("tools I actually trade with").
2. **Single best dashboard architecture:** the right-sized platform of §7 — risk engine at the core, one Home screen first, build order Risk → data → backtest → dashboard → execution, screens added only after live profitability.
3. **Single best edge worth pursuing:** time-series trend-following on liquid crypto majors, with funding-rate carry as the complementary market-neutral sleeve. Both are mechanism-backed, retail-capacity, and testable on free data.
4. **Single highest-probability path to consistent profits:** hypothesis → pessimistic backtest → paper → tiny live → slow scaling, with pre-registered kill criteria and a hard drawdown circuit breaker — i.e., the process, more than any particular signal. Expect single-strategy crypto Sharpe in the 0.7–1.2 range with 20–30% drawdowns, not smooth monthly income; "consistent" at retail means *consistent process and positive multi-year expectancy*, not consistent months.
5. **30-day MVP plan:** §8, week by week.
6. **90-day implementation plan:** §8, month by month.
7. **Brutally honest assessment of the original idea:** As specified — a build-everything intelligence terminal aggregating public research, sentiment, on-chain, macro, and dual-broker execution — it is **likely to fail as a profit-generating system**, for three compounding reasons: (a) it contains no defined, falsifiable edge, and aggregated public information cannot supply one; (b) its scope makes solo completion improbable, and the build itself becomes a procrastination structure that feels like progress; (c) it defers risk management to a future module, which historically is how accounts die. Estimated probability that the terminal *as originally conceived* leads to consistent risk-adjusted profits: **under 10%**. The salvageable 20% of it — funding/OI data, relative-strength baskets, automated risk-checked execution, and your builder skill set — is exactly what the recommended system keeps. The Railgun observation is most likely (~55%) a confounded artifact, plausibly (~35%) a narrower event-driven privacy-catalyst effect, and only ~10% the general edge as stated — and it costs one weekend and zero dollars to find out, which is the only resource allocation it has earned so far.
