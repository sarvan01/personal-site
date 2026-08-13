#!/usr/bin/env python3
"""Log into Milk Road each run and pull indicators + the Analyst Trade Log
into data/milkroad.json (CONTEXT feed, NOT a trading signal).

Your email/password are typed locally via getpass (never echoed to the
terminal, never written to disk, and never sent to Claude -- they go
directly from this script, running on your machine, to Milk Road's own
login endpoint). This replaces manually copying a session cookie from
DevTools each time it expires: you log in fresh every run instead.

HONEST CAVEAT -- this is the least certain piece of the Milk Road
integration. I do not know Milk Road's actual login flow (which auth
provider/framework they use, whether it needs a CSRF token fetched first,
JSON vs form-encoded, or whether the login form has bot protection that
blocks non-browser requests entirely). You configure the real endpoint
once via DevTools (same technique as fetch_milkroad_indicators.py). If the
login POST fails outright, fall back to the cookie-based
fetch_milkroad_indicators.py instead -- log in normally in your browser and
reuse that session's cookie, which doesn't depend on guessing the login
flow at all.

Setup:
    copy scripts\\feeds\\milkroad_login_config.sample.json scripts\\feeds\\milkroad_login_config.json
    notepad scripts\\feeds\\milkroad_login_config.json
    REM paste the login endpoint URL + field names (see docs/milkroad-feed.md)

    REM optional: also set up indicators and/or the trade log to fetch
    REM in the same authenticated run --
    copy scripts\\feeds\\milkroad_endpoints.sample.json scripts\\feeds\\milkroad_endpoints.json
    copy scripts\\feeds\\milkroad_trades_config.sample.json scripts\\feeds\\milkroad_trades_config.json

    python scripts\\feeds\\fetch_milkroad_login.py --debug   (first run: verify it worked)
    python scripts\\feeds\\fetch_milkroad_login.py           (normal run, every time)
"""

import argparse
import getpass
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/feeds -> trading-system
sys.path.insert(0, str(ROOT))
FEEDS_DIR = Path(__file__).resolve().parent

import requests

from fetch_milkroad_indicators import get_path  # reuse the same dotted-path extractor
from trading_system.milkroad import load_milkroad, merge_milkroad, write_milkroad

LOGIN_CONFIG_PATH = FEEDS_DIR / "milkroad_login_config.json"
LOGIN_SAMPLE_PATH = FEEDS_DIR / "milkroad_login_config.sample.json"
INDICATORS_CONFIG_PATH = FEEDS_DIR / "milkroad_endpoints.json"
TRADES_CONFIG_PATH = FEEDS_DIR / "milkroad_trades_config.json"


class LoginError(RuntimeError):
    """Raised for any login failure; main() catches and reports it."""


def load_required_config(path: Path, sample_path: Path, what: str) -> dict:
    if not path.exists():
        raise LoginError(
            f"{path} not found. Copy {sample_path.name} to {path.name} in the "
            f"same folder and fill in your {what} details (see docs/milkroad-feed.md)."
        )
    return json.loads(path.read_text())


def login(config: dict, session: requests.Session, debug: bool,
         email: str, password: str) -> None:
    """POST credentials to Milk Road's login endpoint; the session object
    picks up any Set-Cookie response automatically for subsequent requests."""
    payload = {
        config.get("email_field", "email"): email,
        config.get("password_field", "password"): password,
        **config.get("extra_fields", {}),
    }
    content_type = config.get("content_type", "json")
    kwargs = {"json": payload} if content_type == "json" else {"data": payload}
    try:
        resp = session.post(config["login_url"], timeout=30,
                            headers={"Accept": "application/json"}, **kwargs)
    except requests.RequestException as exc:
        raise LoginError(f"login request failed: {exc}")
    if debug:
        print(f"login response: HTTP {resp.status_code}")
        print(f"cookies received: {list(session.cookies.keys())}")
    if resp.status_code >= 400:
        raise LoginError(
            f"login failed with HTTP {resp.status_code} -- check "
            "milkroad_login_config.json (endpoint URL, field names, content_type), "
            "or the login form may be behind bot protection that blocks this "
            "approach entirely; fall back to fetch_milkroad_indicators.py with a "
            "manually-copied browser cookie instead."
        )
    if not session.cookies:
        raise LoginError(
            "login request succeeded but no session cookie was set -- this "
            "account's auth may not use cookies (e.g. a bearer token in the "
            "response body instead). Re-run with --debug and inspect the "
            "response, or use the cookie-based fetch_milkroad_indicators.py."
        )


def fetch_indicators(session: requests.Session, debug: bool) -> dict:
    if not INDICATORS_CONFIG_PATH.exists():
        print("  (no milkroad_endpoints.json -- skipping indicators)", file=sys.stderr)
        return {}
    config = json.loads(INDICATORS_CONFIG_PATH.read_text())
    today = date.today().isoformat()
    indicators = {}
    for key, spec in config.items():
        url = spec.get("url")
        if not url or "PASTE" in url:
            continue
        try:
            resp = session.get(url, timeout=30, headers={"Accept": "application/json"})
        except requests.RequestException as exc:
            print(f"  {key}: request failed ({exc})", file=sys.stderr)
            continue
        if resp.status_code != 200:
            print(f"  {key}: HTTP {resp.status_code}", file=sys.stderr)
            continue
        try:
            body = resp.json()
        except ValueError:
            print(f"  {key}: response wasn't JSON", file=sys.stderr)
            continue
        if debug:
            print(f"--- {key} raw response (first 1500 chars) ---")
            print(json.dumps(body, indent=2)[:1500])
        value = get_path(body, spec["value_path"]) if spec.get("value_path") else None
        label = get_path(body, spec["label_path"]) if spec.get("label_path") else ""
        if value is None:
            print(f"  {key}: value_path found nothing -- re-run with --debug", file=sys.stderr)
            continue
        indicators[key] = {"value": value, "label": label or "", "as_of": today}
        print(f"  {key}: {value} ({label})")
    return indicators


def fetch_trades(session: requests.Session, debug: bool) -> list:
    if not TRADES_CONFIG_PATH.exists():
        print("  (no milkroad_trades_config.json -- skipping trade log)", file=sys.stderr)
        return []
    config = json.loads(TRADES_CONFIG_PATH.read_text())
    url = config.get("url")
    if not url or "PASTE" in url:
        print("  trades: no URL configured yet, skipping", file=sys.stderr)
        return []
    try:
        resp = session.get(url, timeout=30, headers={"Accept": "application/json"})
    except requests.RequestException as exc:
        print(f"  trades: request failed ({exc})", file=sys.stderr)
        return []
    if resp.status_code != 200:
        print(f"  trades: HTTP {resp.status_code}", file=sys.stderr)
        return []
    try:
        body = resp.json()
    except ValueError:
        print("  trades: response wasn't JSON", file=sys.stderr)
        return []
    if debug:
        print("--- trades raw response (first 1500 chars) ---")
        print(json.dumps(body, indent=2)[:1500])

    records = get_path(body, config["records_path"]) if config.get("records_path") else body
    if not isinstance(records, list):
        print("  trades: records_path did not resolve to a list -- re-run with --debug",
              file=sys.stderr)
        return []

    trades = []
    for rec in records[:20]:
        date_v = get_path(rec, config["date_path"]) if config.get("date_path") else None
        action_v = get_path(rec, config["action_path"]) if config.get("action_path") else None
        asset_v = get_path(rec, config["asset_path"]) if config.get("asset_path") else None
        if not (date_v and action_v and asset_v):
            continue
        trade = {
            "date": str(date_v)[:10],
            "action": str(action_v).upper(),
            "asset": str(asset_v),
            "note": str(get_path(rec, config["note_path"]) or "") if config.get("note_path") else "",
            "source": "milkroad.com",
        }
        if config.get("analyst_path"):
            analyst = get_path(rec, config["analyst_path"])
            if analyst:
                trade["analyst"] = str(analyst)
        if config.get("perf_path"):
            perf = get_path(rec, config["perf_path"])
            if perf is not None:
                try:
                    trade["perf_pct"] = float(perf)
                except (TypeError, ValueError):
                    pass
        trades.append(trade)
    print(f"  trades: {len(trades)} parsed")
    return trades


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                        help="print login status and each endpoint's raw JSON")
    args = parser.parse_args()

    try:
        login_config = load_required_config(LOGIN_CONFIG_PATH, LOGIN_SAMPLE_PATH, "login")
    except LoginError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("Milk Road login (typed locally -- never sent to Claude, never saved to disk)")
    email = input("  email: ").strip()
    password = getpass.getpass("  password: ")

    session = requests.Session()
    try:
        login(login_config, session, args.debug, email, password)
    except LoginError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print("logged in.")

    indicators = fetch_indicators(session, args.debug)
    trades = fetch_trades(session, args.debug)

    if not indicators and not trades:
        print("\nnothing fetched -- see warnings above.", file=sys.stderr)
        return 1

    updates = {
        "source": "milkroad.com",
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    if indicators:
        updates["indicators"] = indicators
    if trades:
        updates["trades"] = trades
    data = merge_milkroad(load_milkroad(), updates)
    path = write_milkroad(data)
    print(f"\nwrote -> {path}")
    print("run: python scripts/cockpit.py --config h1b   (to show it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
