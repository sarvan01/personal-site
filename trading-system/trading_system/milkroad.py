"""Milk Road context feed (DISPLAY ONLY).

This is CONTEXT for the human, NOT a trading signal. Nothing here touches the
strategy, the risk engine, or the paper account. If Milk Road data should ever
influence trades, it must first become a pre-registered hypothesis, gated
exactly like H1b/H3 — see docs/trading-system-analysis.md §7 (sentiment).

The cockpit reads data/milkroad.json (schema in docs/milkroad-feed.md). You
populate it however you judge ToS-compliant — manually, or with the templates
in scripts/feeds/. Milk Road has no public API and its data pages are premium,
so automation is at your discretion.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MILKROAD_PATH = ROOT / "data" / "milkroad.json"

INDICATOR_ORDER = ("macro_index", "macro_pulse", "crypto_pulse")
VALID_ACTIONS = ("BUY", "SELL", "HOLD", "WATCH", "TRIM", "ADD")


def load_milkroad(path: Path = MILKROAD_PATH) -> dict | None:
    """Load the context feed, or None if absent/unreadable (never raises)."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def write_milkroad(data: dict, path: Path = MILKROAD_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault(
        "updated_utc", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    path.write_text(json.dumps(data, indent=2))
    return path


def merge_milkroad(existing: dict | None, updates: dict) -> dict:
    """Merge partial updates without clobbering the other section — so the
    Discord template can fill `trades` while the indicators template fills
    `indicators`, independently."""
    out = dict(existing or {})
    if "indicators" in updates:
        out.setdefault("indicators", {})
        out["indicators"] = {**out["indicators"], **updates["indicators"]}
    if "trades" in updates:
        out["trades"] = updates["trades"]
    for k in ("updated_utc", "source"):
        if k in updates:
            out[k] = updates[k]
    return out


def sample_milkroad() -> dict:
    """Illustrative sample used for the offline demo and as a schema example."""
    return {
        "updated_utc": "sample",
        "source": "sample",
        "indicators": {
            "macro_index": {"value": 62, "label": "Risk-On", "as_of": "2026-06-13"},
            "macro_pulse": {"value": 54, "label": "Neutral+", "as_of": "2026-06-13"},
            "crypto_pulse": {"value": 71, "label": "Greed", "as_of": "2026-06-13"},
        },
        "trades": [
            {"date": "2026-06-12", "action": "BUY", "asset": "SOL",
             "note": "adding to core position", "source": "discord"},
            {"date": "2026-06-11", "action": "HOLD", "asset": "BTC",
             "note": "", "source": "discord"},
            {"date": "2026-06-09", "action": "WATCH", "asset": "LINK",
             "note": "waiting for reclaim of range", "source": "discord"},
        ],
    }
