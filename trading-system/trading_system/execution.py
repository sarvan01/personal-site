"""Execution layer (report section 7).

Turns target weights into orders on Binance Spot. THREE venues:

  - DRY     (default): no network, no orders. Simulates fills against a local
            balance file so you can see exactly what WOULD be sent.
  - TESTNET: places real orders on Binance Spot Testnet
            (https://testnet.binance.vision) with play money. This is where
            the system lives during validation.
  - LIVE:   real money. Hard-gated: requires BOTH the env var
            ALLOW_LIVE_TRADING=yes AND the explicit i_understand_live=True
            argument. Never reachable by accident.

Every order is routed through the SAME risk checks the backtest and paper
account use (per-asset cap, gross cap, circuit-breaker scale). The executor
never invents a position the risk engine would not allow.

This module places NO live orders unless you deliberately select LIVE and
clear both gates. Testnet-first is the intended path.
"""

import hashlib
import hmac
import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from urllib.parse import urlencode

import requests

from .config import RiskConfig

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
EXECUTION_LOG = OUT_DIR / "execution_log.json"
DRY_STATE = OUT_DIR / "dry_account.json"

TESTNET_BASE = "https://testnet.binance.vision"
LIVE_BASE = "https://api.binance.com"

# Minimum order value Binance accepts (USDT). Deltas smaller than the
# rebalance band below are skipped to avoid churning dust.
MIN_NOTIONAL = 10.0

# Signed-request timing. Binance rejects timestamps AHEAD of server time
# (-1021); recvWindow only tolerates late arrivals, so we aim slightly
# behind exchange time and allow a generous window for latency.
RECV_WINDOW_MS = 10_000
TIME_SAFETY_MS = 500


class Venue(str, Enum):
    DRY = "dry"
    TESTNET = "testnet"
    LIVE = "live"


class ExecutionError(RuntimeError):
    pass


@dataclass
class OrderPlan:
    symbol: str
    side: str  # BUY / SELL
    target_weight: float
    current_weight: float
    notional: float  # USDT value of the trade
    price: float
    reason: str = "rebalance"

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "target_weight": round(self.target_weight, 6),
            "current_weight": round(self.current_weight, 6),
            "notional": round(self.notional, 2),
            "price": self.price,
            "reason": self.reason,
        }


# --------------------------------------------------------------------------
# Brokers
# --------------------------------------------------------------------------
class DryRunBroker:
    """Offline simulator. Holds a JSON balance; 'fills' update it at the
    provided price. No network, ever. The default and the test backend."""

    def __init__(self, prices: dict[str, float], state_path: Path = DRY_STATE,
                 start_usdt: float = 10_000.0):
        self.prices = prices
        self.state_path = state_path
        if state_path.exists():
            self.state = json.loads(state_path.read_text())
        else:
            self.state = {"USDT": start_usdt}
        self.name = "DRY"

    def price(self, symbol: str) -> float:
        return self.prices[symbol]

    def holdings(self) -> dict[str, float]:
        return {k: v for k, v in self.state.items() if k != "USDT"}

    def equity(self, relevant_bases: set | None = None) -> float:
        eq = self.state.get("USDT", 0.0)
        for base, qty in self.holdings().items():
            eq += qty * self.prices.get(base + "USDT", 0.0)
        return eq

    def market_order(self, symbol: str, side: str, notional: float) -> dict:
        price = self.prices[symbol]
        base = symbol.replace("USDT", "")
        qty = notional / price
        if side == "BUY":
            self.state["USDT"] = self.state.get("USDT", 0.0) - notional
            self.state[base] = self.state.get(base, 0.0) + qty
        else:
            self.state["USDT"] = self.state.get("USDT", 0.0) + notional
            self.state[base] = self.state.get(base, 0.0) - qty
        return {"symbol": symbol, "side": side, "price": price, "qty": qty,
                "notional": notional, "simulated": True}

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2))


class BinanceSpotBroker:
    """Signed REST client for Binance Spot testnet or live."""

    def __init__(self, venue: Venue, key: str, secret: str):
        self.venue = venue
        self.key = key
        self.secret = secret
        self.base = TESTNET_BASE if venue == Venue.TESTNET else LIVE_BASE
        self.name = venue.value.upper()
        self._price_cache: dict[str, float] = {}
        self._balances_cache: dict[str, float] | None = None
        self._time_offset: int | None = None
        self._filter_cache: dict[str, dict] = {}

    def _filters(self, symbol: str) -> dict:
        """Per-symbol exchange filters (LOT_SIZE step/min qty, min notional).

        Binance rejects orders whose quantity isn't a multiple of stepSize or
        whose value is below minNotional -- and these differ per symbol (BTC
        steps in 0.00001, XRP in whole units). Cached per symbol; degrades to
        permissive defaults if exchangeInfo is unreachable, in which case the
        exchange itself remains the final validator.
        """
        if symbol in self._filter_cache:
            return self._filter_cache[symbol]
        out = {"step_size": 0.0, "min_qty": 0.0, "min_notional": 0.0}
        try:
            resp = requests.get(f"{self.base}/api/v3/exchangeInfo",
                                params={"symbol": symbol}, timeout=15)
            if resp.status_code == 200:
                for f in resp.json()["symbols"][0]["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        out["step_size"] = float(f["stepSize"])
                        out["min_qty"] = float(f["minQty"])
                    elif f["filterType"] in ("NOTIONAL", "MIN_NOTIONAL"):
                        out["min_notional"] = float(
                            f.get("minNotional", f.get("notional", 0.0)))
        except (requests.RequestException, KeyError, IndexError, ValueError):
            print(f"warning: exchangeInfo unavailable for {symbol}; "
                  "using permissive lot sizing (exchange will validate)")
        self._filter_cache[symbol] = out
        return out

    @staticmethod
    def _quantize(qty: float, step: float) -> float:
        """Floor qty to a multiple of step (Binance rejects anything else)."""
        if step <= 0:
            return round(qty, 8)
        # int() floors toward zero; add a tiny epsilon so a qty that is
        # already an exact multiple isn't knocked down a step by float error.
        return int(qty / step + 1e-9) * step

    def _sync_time(self) -> int:
        """Offset (ms) between the exchange's clock and this machine's.

        Binance rejects any signed request whose timestamp is AHEAD of server
        time (error -1021) -- and recvWindow does NOT help, since it only
        tolerates requests arriving late. An unattended daily job on a PC
        whose clock drifts by a second would otherwise fail every run, so we
        stamp requests in exchange time rather than local time.
        """
        try:
            resp = requests.get(f"{self.base}/api/v3/time", timeout=15)
            if resp.status_code == 200:
                local_ms = int(time.time() * 1000)
                self._time_offset = int(resp.json()["serverTime"]) - local_ms
                if abs(self._time_offset) > 2000:
                    print(f"note: local clock differs from exchange by "
                          f"{self._time_offset} ms; using exchange time. "
                          "Consider syncing Windows time (w32tm /resync).")
                return self._time_offset
        except (requests.RequestException, KeyError, ValueError) as exc:
            print(f"warning: could not sync exchange time ({exc}); "
                  "using local clock", file=sys.stderr)
        self._time_offset = 0
        return 0

    def _signed(self, method: str, path: str, params: dict,
                _retry: bool = True) -> dict:
        if self._time_offset is None:
            self._sync_time()
        params = dict(params)
        # Stamp in exchange time, minus a small safety margin: being slightly
        # BEHIND is absorbed by recvWindow, being ahead is fatal.
        params["timestamp"] = int(time.time() * 1000) + self._time_offset - TIME_SAFETY_MS
        params["recvWindow"] = RECV_WINDOW_MS
        query = urlencode(params)
        sig = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base}{path}?{query}&signature={sig}"
        headers = {"X-MBX-APIKEY": self.key}
        resp = requests.request(method, url, headers=headers, timeout=15)
        if resp.status_code != 200:
            # -1021 = timestamp outside the accepted window. Clocks can drift
            # mid-run (or the cached offset went stale); resync once and retry
            # before failing the day's execution.
            if _retry and '-1021' in resp.text:
                print("timestamp rejected (-1021); resyncing exchange time and retrying")
                self._sync_time()
                clean = {k: v for k, v in params.items()
                         if k not in ("timestamp", "recvWindow")}
                return self._signed(method, path, clean, _retry=False)
            raise ExecutionError(f"{method} {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def _all_prices(self) -> dict[str, float]:
        """ALL tickers in ONE request, cached for this run. The per-asset
        price loop this replaces made one serial HTTP call per held asset --
        on testnet (slow API + ~10 pre-funded play assets) that looked like a
        hang."""
        if not self._price_cache:
            resp = requests.get(f"{self.base}/api/v3/ticker/price", timeout=20)
            if resp.status_code != 200:
                raise ExecutionError(f"batch prices: HTTP {resp.status_code}")
            self._price_cache = {d["symbol"]: float(d["price"])
                                 for d in resp.json()}
        return self._price_cache

    def price(self, symbol: str) -> float:
        try:
            p = self._all_prices().get(symbol)
            if p is not None:
                return p
        except ExecutionError:
            pass  # batch endpoint hiccup: fall through to a single lookup
        resp = requests.get(f"{self.base}/api/v3/ticker/price",
                            params={"symbol": symbol}, timeout=15)
        if resp.status_code != 200:
            raise ExecutionError(f"price {symbol}: {resp.text}")
        return float(resp.json()["price"])

    def _balances(self) -> dict[str, float]:
        if self._balances_cache is None:
            acct = self._signed("GET", "/api/v3/account", {})
            self._balances_cache = {
                b["asset"]: float(b["free"]) + float(b["locked"])
                for b in acct["balances"]
                if float(b["free"]) + float(b["locked"]) > 0
            }
        return self._balances_cache

    def holdings(self) -> dict[str, float]:
        return {k: v for k, v in self._balances().items() if k != "USDT"}

    def equity(self, relevant_bases: set | None = None) -> float:
        """Account equity in USDT terms.

        relevant_bases scopes the calculation to the assets the system
        actually manages (its universe) plus USDT -- pre-funded testnet play
        assets the system will never trade (LTC, TRX, ...) would otherwise
        inflate the denominator and shrink every target weight."""
        bals = self._balances()
        prices = self._all_prices()
        eq = bals.get("USDT", 0.0)
        for asset, qty in bals.items():
            if asset == "USDT":
                continue
            if relevant_bases is not None and asset not in relevant_bases:
                continue
            p = prices.get(asset + "USDT")
            if p:
                eq += qty * p
        return eq

    def market_order(self, symbol: str, side: str, notional: float) -> dict:
        filters = self._filters(symbol)
        if filters["min_notional"] and notional < filters["min_notional"]:
            raise ExecutionError(
                f"{symbol}: notional ${notional:.2f} below exchange minimum "
                f"${filters['min_notional']:.2f} -- skipping")
        params = {"symbol": symbol, "side": side, "type": "MARKET"}
        if side == "BUY":
            params["quoteOrderQty"] = round(notional, 2)
        else:
            qty = self._quantize(notional / self.price(symbol), filters["step_size"])
            if qty <= 0 or (filters["min_qty"] and qty < filters["min_qty"]):
                raise ExecutionError(
                    f"{symbol}: quantized qty {qty} below exchange minimum "
                    f"{filters['min_qty']} -- skipping")
            # Format without scientific notation; trim trailing zeros.
            params["quantity"] = f"{qty:.8f}".rstrip("0").rstrip(".")
        return self._signed("POST", "/api/v3/order", params)


# --------------------------------------------------------------------------
# Executor
# --------------------------------------------------------------------------
@dataclass
class Executor:
    broker: object
    risk: RiskConfig
    rebalance_band: float = 0.01  # ignore weight drifts smaller than 1% of equity
    breaker_scale: float = 1.0  # pass the circuit-breaker scale from the daily run
    log_path: Path = field(default=EXECUTION_LOG)

    def pre_trade_checks(self, targets: dict[str, float]) -> None:
        """Reject a target set that violates the risk policy BEFORE any order.

        Per-asset violations and negative weights indicate an upstream bug and
        fail closed. A gross overflow is NOT rejected here -- it is expected
        geometry (every asset can hit its individual cap at once in calm
        markets) and plan() scales it to max_gross exactly as the backtest
        does; the gross check below is only a backstop that should never fire
        after that scaling.
        """
        for sym, w in targets.items():
            if w < 0:
                raise ExecutionError(f"{sym}: negative target weight {w} (no shorting)")
            if w > self.risk.max_asset_weight + 1e-9:
                raise ExecutionError(
                    f"{sym}: target {w:.1%} exceeds max_asset_weight "
                    f"{self.risk.max_asset_weight:.1%}")
        gross = sum(targets.values())
        if gross > self.risk.max_gross + 1e-6:
            raise ExecutionError(
                f"gross exposure {gross:.1%} exceeds max_gross after capping -- "
                "upstream sizing bug, refusing to trade")

    def plan(self, targets: dict[str, float]) -> list[OrderPlan]:
        """Diff desired weights against current holdings -> order plans.

        Targets are scaled by the circuit-breaker first (breaker flat => all
        targets 0 => sells to cash), then by the portfolio gross cap
        (proportional, mirroring the backtest's target_weights).
        """
        from .risk import cap_gross

        scaled = {s: w * self.breaker_scale for s, w in targets.items()}
        scaled, gross_scale = cap_gross(scaled, self.risk.max_gross)
        if gross_scale < 1.0:
            print(f"gross cap applied: targets scaled by {gross_scale:.3f} "
                  f"to fit max_gross {self.risk.max_gross:.0%}")
        self.pre_trade_checks(scaled)
        bases = {s.replace("USDT", "") for s in scaled}
        equity = self.broker.equity(relevant_bases=bases)
        if equity <= 0:
            raise ExecutionError("non-positive equity; refusing to trade")
        holdings = self.broker.holdings()
        plans: list[OrderPlan] = []
        for sym, target_w in scaled.items():
            price = self.broker.price(sym)
            base = sym.replace("USDT", "")
            cur_val = holdings.get(base, 0.0) * price
            cur_w = cur_val / equity
            delta_w = target_w - cur_w
            notional = abs(delta_w) * equity
            if notional < max(MIN_NOTIONAL, self.rebalance_band * equity):
                continue  # within band: leave it alone
            plans.append(OrderPlan(
                symbol=sym,
                side="BUY" if delta_w > 0 else "SELL",
                target_weight=target_w,
                current_weight=cur_w,
                notional=notional,
                price=price,
                reason="breaker-flat" if self.breaker_scale == 0 else "rebalance",
            ))
        return plans

    def execute(self, targets: dict[str, float], dry_preview: bool = False) -> dict:
        plans = self.plan(targets)
        results = []
        for p in plans:
            if dry_preview:
                results.append({**p.as_dict(), "status": "preview"})
                continue
            try:
                fill = self.broker.market_order(p.symbol, p.side, p.notional)
            except ExecutionError as exc:
                # One symbol's dust/min-notional skip must not abort the
                # rest of the day's rebalance; record it and continue.
                print(f"  {p.symbol}: order skipped ({exc})")
                results.append({**p.as_dict(), "status": "skipped", "error": str(exc)})
                continue
            results.append({**p.as_dict(), "status": "filled", "fill": fill})
        record = {
            "ts": int(time.time()),
            "venue": self.broker.name,
            "breaker_scale": self.breaker_scale,
            "equity": self.broker.equity(),
            "orders": results,
        }
        self._append_log(record)
        if hasattr(self.broker, "save"):
            self.broker.save()
        return record

    def _append_log(self, record: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if self.log_path.exists():
            history = json.loads(self.log_path.read_text())
        history.append(record)
        self.log_path.write_text(json.dumps(history, indent=2))


def make_broker(venue: Venue, prices: dict | None = None,
                i_understand_live: bool = False, env: dict | None = None):
    """Construct a broker for the chosen venue, enforcing the live gate."""
    import os
    env = env if env is not None else dict(os.environ)

    if venue == Venue.DRY:
        return DryRunBroker(prices or {})

    key = env.get("BINANCE_KEY", "")
    secret = env.get("BINANCE_SECRET", "")
    if not key or not secret:
        raise ExecutionError(
            f"{venue.value}: set BINANCE_KEY and BINANCE_SECRET env vars "
            "(testnet keys from https://testnet.binance.vision)")

    if venue == Venue.LIVE:
        if env.get("ALLOW_LIVE_TRADING", "").lower() != "yes":
            raise ExecutionError(
                "LIVE blocked: set env ALLOW_LIVE_TRADING=yes to enable real money")
        if not i_understand_live:
            raise ExecutionError(
                "LIVE blocked: pass --i-understand-live to confirm real-money orders")

    return BinanceSpotBroker(venue, key, secret)


def observed_cost_bps(symbol: str, expected_price: float, order_response: dict) -> float | None:
    """Realized per-side cost in bps for a filled Binance order: slippage of
    the fill VWAP vs the pre-trade reference price, plus commissions.

    This is what feeds the reconciliation that gates LIVE -- the kill
    criterion retires the strategy if observed costs exceed 1.5x the assumed
    25 bps/side. Returns None when the response carries no fill details
    (e.g. dry-run simulations). Commission paid in an asset other than USDT
    or the symbol's base (e.g. BNB fee discount) is skipped, slightly
    UNDERSTATING cost -- acceptable because the assumed figure is already
    deliberately pessimistic.
    """
    fills = (order_response or {}).get("fills") or []
    if not fills or not expected_price or expected_price <= 0:
        return None
    qty = sum(float(f.get("qty", 0)) for f in fills)
    if qty <= 0:
        return None
    vwap = sum(float(f["price"]) * float(f["qty"]) for f in fills) / qty
    notional = vwap * qty
    slippage = abs(vwap - expected_price) / expected_price

    base = symbol.replace("USDT", "")
    commission_usdt = 0.0
    for f in fills:
        c = float(f.get("commission", 0) or 0)
        if c <= 0:
            continue
        asset = f.get("commissionAsset", "")
        if asset == "USDT":
            commission_usdt += c
        elif asset == base:
            commission_usdt += c * vwap
    commission_frac = commission_usdt / notional if notional > 0 else 0.0
    return (slippage + commission_frac) * 10_000
