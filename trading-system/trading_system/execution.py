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

    def equity(self) -> float:
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

    def _signed(self, method: str, path: str, params: dict) -> dict:
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        query = urlencode(params)
        sig = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base}{path}?{query}&signature={sig}"
        headers = {"X-MBX-APIKEY": self.key}
        resp = requests.request(method, url, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise ExecutionError(f"{method} {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def price(self, symbol: str) -> float:
        resp = requests.get(f"{self.base}/api/v3/ticker/price",
                            params={"symbol": symbol}, timeout=15)
        if resp.status_code != 200:
            raise ExecutionError(f"price {symbol}: {resp.text}")
        p = float(resp.json()["price"])
        self._price_cache[symbol] = p
        return p

    def _balances(self) -> dict[str, float]:
        acct = self._signed("GET", "/api/v3/account", {})
        return {
            b["asset"]: float(b["free"]) + float(b["locked"])
            for b in acct["balances"]
            if float(b["free"]) + float(b["locked"]) > 0
        }

    def holdings(self) -> dict[str, float]:
        return {k: v for k, v in self._balances().items() if k != "USDT"}

    def equity(self) -> float:
        bals = self._balances()
        eq = bals.get("USDT", 0.0)
        for asset, qty in bals.items():
            if asset == "USDT":
                continue
            try:
                eq += qty * self.price(asset + "USDT")
            except ExecutionError:
                continue  # asset without a USDT pair; ignore
        return eq

    def market_order(self, symbol: str, side: str, notional: float) -> dict:
        params = {"symbol": symbol, "side": side, "type": "MARKET"}
        if side == "BUY":
            params["quoteOrderQty"] = round(notional, 2)
        else:
            qty = notional / self.price(symbol)
            params["quantity"] = round(qty, 5)  # simplified lot sizing
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
        """Reject a target set that violates the risk policy BEFORE any order."""
        for sym, w in targets.items():
            if w < 0:
                raise ExecutionError(f"{sym}: negative target weight {w} (no shorting)")
            if w > self.risk.max_asset_weight + 1e-9:
                raise ExecutionError(
                    f"{sym}: target {w:.1%} exceeds max_asset_weight "
                    f"{self.risk.max_asset_weight:.1%}")
        gross = sum(targets.values())
        if gross > self.risk.max_gross + 1e-9:
            raise ExecutionError(
                f"gross exposure {gross:.1%} exceeds max_gross {self.risk.max_gross:.1%}")

    def plan(self, targets: dict[str, float]) -> list[OrderPlan]:
        """Diff desired weights against current holdings -> order plans.

        Targets are scaled by the circuit-breaker first: if the breaker is
        flat (scale 0), every target becomes 0 and the system sells to cash.
        """
        scaled = {s: w * self.breaker_scale for s, w in targets.items()}
        self.pre_trade_checks(scaled)
        equity = self.broker.equity()
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
            fill = self.broker.market_order(p.symbol, p.side, p.notional)
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
