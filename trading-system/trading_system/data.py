"""Data layer.

Live fetching uses Binance public endpoints (spot klines and perp funding).
Some networks (including cloud sandboxes) block Binance; everything else in
the system works from cached CSVs in ``data/`` or from the synthetic
generator, so the backtester and tests never need network access.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SPOT_BASES = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
]
FUTURES_BASE = "https://fapi.binance.com"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

KLINE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume"]


class DataError(RuntimeError):
    pass


def _get(url: str, params: dict) -> list:
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            last_err = DataError(f"HTTP {resp.status_code} from {url}")
        except requests.RequestException as exc:  # network-level failure
            last_err = exc
        time.sleep(2**attempt)
    raise DataError(f"failed to fetch {url}: {last_err}")


def fetch_daily_klines(symbol: str, start: str = "2017-01-01") -> pd.DataFrame:
    """Fetch full daily kline history for `symbol`, paginated 1000 at a time."""
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    rows: list[list] = []
    for base in SPOT_BASES:
        try:
            cursor = start_ms
            while True:
                batch = _get(
                    f"{base}/api/v3/klines",
                    {
                        "symbol": symbol,
                        "interval": "1d",
                        "startTime": cursor,
                        "limit": 1000,
                    },
                )
                if not batch:
                    break
                rows.extend(batch)
                if len(batch) < 1000:
                    break
                cursor = batch[-1][0] + 1
            break
        except DataError:
            rows = []
            continue
    if not rows:
        raise DataError(f"could not fetch klines for {symbol} from any base URL")
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = KLINE_COLUMNS
    df["date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.normalize()
    df = df.set_index("date")[["open", "high", "low", "close", "volume"]].astype(float)
    # Drop today's still-forming bar.
    return df[df.index < pd.Timestamp.now(tz="UTC").normalize()]


def fetch_funding(symbol: str, start: str = "2020-01-01") -> pd.Series:
    """Fetch perp funding-rate history (8h periods) for `symbol`."""
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    rows: list[dict] = []
    cursor = start_ms
    while True:
        batch = _get(
            f"{FUTURES_BASE}/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": cursor, "limit": 1000},
        )
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        cursor = batch[-1]["fundingTime"] + 1
    if not rows:
        raise DataError(f"could not fetch funding for {symbol}")
    df = pd.DataFrame(rows)
    idx = pd.to_datetime(df["fundingTime"].astype(int), unit="ms", utc=True)
    return pd.Series(df["fundingRate"].astype(float).values, index=idx, name=symbol)


def cache_path(symbol: str, kind: str) -> Path:
    return DATA_DIR / f"{symbol}_{kind}.csv"


def save_csv(df: pd.DataFrame | pd.Series, symbol: str, kind: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(symbol, kind)
    df.to_csv(path)
    return path


def load_klines(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol, "1d")
    if not path.exists():
        raise DataError(
            f"no cached data for {symbol}; run scripts/fetch_data.py first"
        )
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df.astype(float)


def synthetic_klines(
    days: int = 2200, seed: int = 7, start: str = "2019-01-01"
) -> pd.DataFrame:
    """Regime-switching geometric random walk for offline demos and tests.

    Alternates bull / chop / bear segments so trend signals, the regime
    engine, and the circuit breakers all get exercised. Not a substitute for
    real data — it exists so the pipeline can be validated end to end
    without network access.
    """
    rng = np.random.default_rng(seed)
    segments = []
    remaining = days
    drifts = [0.0025, -0.0015, 0.0002, 0.003, -0.0025, 0.0]
    vols = [0.03, 0.045, 0.02, 0.035, 0.05, 0.025]
    i = 0
    while remaining > 0:
        seg_len = min(int(rng.integers(120, 400)), remaining)
        mu, sigma = drifts[i % len(drifts)], vols[i % len(vols)]
        segments.append(rng.normal(mu, sigma, seg_len))
        remaining -= seg_len
        i += 1
    rets = np.concatenate(segments)
    close = 10_000 * np.exp(np.cumsum(rets))
    index = pd.date_range(start, periods=days, freq="D", tz="UTC")
    intraday = np.abs(rng.normal(0, 0.01, days))
    df = pd.DataFrame(
        {
            "open": close * (1 + rng.normal(0, 0.003, days)),
            "high": close * (1 + intraday),
            "low": close * (1 - intraday),
            "close": close,
            "volume": rng.uniform(1e4, 5e4, days),
        },
        index=index,
    )
    df.index.name = "date"
    return df


def synthetic_funding(days: int = 800, seed: int = 11) -> pd.Series:
    """Synthetic 8h funding series with hot and cold stretches."""
    rng = np.random.default_rng(seed)
    n = days * 3
    base = np.full(n, 0.0001)  # the structural 0.01%-per-8h default
    hot = rng.random(n) < 0.2
    base[hot] += rng.uniform(0.0002, 0.0008, hot.sum())
    cold = rng.random(n) < 0.1
    base[cold] = rng.uniform(-0.0003, 0.0, cold.sum())
    index = pd.date_range("2023-01-01", periods=n, freq="8h", tz="UTC")
    return pd.Series(base, index=index, name="funding")
