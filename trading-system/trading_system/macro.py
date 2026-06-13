"""Optional macro inputs for the regime engine's stress axis (report section 7):
DXY trend, real yields (FRED), and aggregate stablecoin market cap (DefiLlama).

All inputs are OPTIONAL: the regime engine runs without them, and every
fetcher degrades gracefully when the network is unavailable. Synthetic
generators exist so the cockpit and tests work offline.
"""

import io

import numpy as np
import pandas as pd
import requests

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
DEFILLAMA_STABLES = "https://stablecoins.llama.fi/stablecoincharts/all"
# Stooq serves ^VIX daily history as plain CSV with no key — more reliable
# than FRED's CSV endpoint, which intermittently 504s.
STOOQ_VIX = "https://stooq.com/q/d/l/?s=%5Evix&i=d"

# FRED series: broad dollar index, 10y TIPS (real) yield, CBOE VIX.
DXY_SERIES = "DTWEXBGS"
REAL_YIELD_SERIES = "DFII10"
VIX_SERIES = "VIXCLS"


class MacroError(RuntimeError):
    pass


def fetch_fred(series: str) -> pd.Series:
    try:
        df = pd.read_csv(FRED_CSV.format(series=series), na_values=".")
    except Exception as exc:
        raise MacroError(f"FRED fetch failed for {series}: {exc}")
    df.columns = ["date", "value"]
    s = pd.Series(
        df["value"].astype(float).values,
        index=pd.to_datetime(df["date"], utc=True),
        name=series,
    )
    return s.dropna()


def parse_stooq_csv(text: str) -> pd.Series:
    """Stooq CSV (Date,Open,High,Low,Close,Volume) -> daily Close Series."""
    df = pd.read_csv(io.StringIO(text))
    if "Close" not in df.columns or "Date" not in df.columns:
        raise MacroError(f"unexpected Stooq columns: {list(df.columns)}")
    s = pd.Series(
        df["Close"].astype(float).values,
        index=pd.to_datetime(df["Date"], utc=True),
        name="VIX",
    )
    return s.dropna()


def fetch_vix_stooq() -> pd.Series:
    """Fetch ^VIX daily close history from Stooq (free, no key)."""
    try:
        resp = requests.get(STOOQ_VIX, timeout=30)
    except requests.RequestException as exc:
        raise MacroError(f"Stooq VIX fetch failed: {exc}")
    if resp.status_code != 200 or not resp.text.lstrip().startswith("Date"):
        raise MacroError(f"Stooq VIX fetch failed: HTTP {resp.status_code} {resp.text[:80]}")
    return parse_stooq_csv(resp.text)


def fetch_stablecoin_mcap() -> pd.Series:
    try:
        rows = requests.get(DEFILLAMA_STABLES, timeout=15).json()
    except Exception as exc:
        raise MacroError(f"DefiLlama fetch failed: {exc}")
    idx = pd.to_datetime([int(r["date"]) for r in rows], unit="s", utc=True)
    vals = [r.get("totalCirculatingUSD", {}).get("peggedUSD", np.nan) for r in rows]
    return pd.Series(vals, index=idx, name="stablecoin_mcap").dropna()


def macro_risk_off(
    dxy: pd.Series | None = None,
    real_yield: pd.Series | None = None,
    stable_mcap: pd.Series | None = None,
    index: pd.DatetimeIndex | None = None,
) -> pd.Series | None:
    """Composite risk-off flag: at least 2 of 3 components risk-off.

    Components (each a boolean daily series):
      - DXY above its 60-day mean (dollar strengthening)
      - 10y real yield rising over 60 days
      - aggregate stablecoin market cap shrinking over 30 days
    Returns None when no inputs are available (regime engine then ignores it).
    """
    votes = []
    if dxy is not None and len(dxy) > 60:
        votes.append(dxy > dxy.rolling(60, min_periods=60).mean())
    if real_yield is not None and len(real_yield) > 60:
        votes.append(real_yield.diff(60) > 0)
    if stable_mcap is not None and len(stable_mcap) > 30:
        votes.append(stable_mcap.pct_change(30) < 0)
    if not votes:
        return None
    frame = pd.concat(votes, axis=1).ffill()
    if index is not None:
        frame = frame.reindex(index, method="ffill")
    needed = 2 if len(votes) >= 2 else 1
    return (frame.fillna(False).sum(axis=1) >= needed).rename("macro_risk_off")


def synthetic_macro(days: int = 1500, seed: int = 21, start: str = "2019-01-01"):
    """Random-walk DXY / real yield / stablecoin mcap for offline runs."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days, freq="D", tz="UTC")
    dxy = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.002, days))), index=idx)
    ry = pd.Series(np.cumsum(rng.normal(0, 0.01, days)), index=idx)
    stables = pd.Series(
        1.2e11 * np.exp(np.cumsum(rng.normal(0.0002, 0.002, days))), index=idx
    )
    return dxy, ry, stables
