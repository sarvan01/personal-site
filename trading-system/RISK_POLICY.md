# Risk Policy (one page, pre-registered)

This policy was written before the first backtest result was seen. Any change
to it requires a dated entry in `research/hypothesis_log.json` explaining why,
written **before** the change takes effect.

## Position rules

1. Per-trade risk to stop: **<= 0.5% of equity** (ATR-based stop, 3x ATR(20)).
2. Max single-asset exposure: **25%** of equity.
3. Max gross exposure: **100%** (no leverage on the directional sleeve).
4. Portfolio vol target: **12% annualized**; positions sized down when
   realized vol rises.
5. Carry sleeve: **<= 30%** of account, **>= 3x** maintenance-margin buffer on
   the perp short leg.
6. Long/flat only on alts. No shorting alts. No memecoins in Sleeve A.

## Circuit breakers (non-negotiable)

- **-10%** peak-to-trough equity drawdown: halve all position sizes.
- **-15%**: go flat. Stay flat 30 trading days. Resume at half size only after
  a written post-mortem; full size only at a new equity high.

## Kill criteria (pre-registered)

Retire a strategy if **either**:

- 12-month live Sharpe < 0 **and** live costs exceed backtest assumptions by
  more than 50%, or
- the strategy's premise is invalidated (e.g., funding structurally negative
  for 6+ months for the carry sleeve).

## Process rules

- Every order goes through the risk engine's pre-trade checks. No manual
  orders outside the system. Manual override count target: **zero**; every
  override is logged and reviewed in the weekly 30-minute ritual.
- Live capital only after: real-data backtest gate PASS, 4 clean paper weeks,
  observed costs within 1.5x of assumptions.
- Scale-up path: 10% of target size for 3 months, then 50%, then 100% — each
  step requires the reconciliation report to stay within bounds.

## Venue risk

- Binance for crypto execution; IBKR holds non-deployed capital in T-bill
  ETFs / money market. Never more than the crypto sleeves' capital on any
  single crypto venue.
