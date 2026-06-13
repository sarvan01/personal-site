"""The cockpit: one self-contained HTML page that aggregates everything —
regime, signals, carry, risk and breaker state, paper account equity,
backtest grid verdict, walk-forward, the Railgun event study, cost
reconciliation, the hypothesis log, and 30-day plan progress.

It renders from plain dicts so it works identically on synthetic or real
data, and never needs a web server: open out/cockpit.html in a browser.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
HYPOTHESIS_LOG = ROOT / "research" / "hypothesis_log.json"

CSS = """
 body { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background:#0d1117;
        color:#d0d7de; max-width:1100px; margin:1.5rem auto; padding:0 1rem; font-size:14px; }
 h1 { font-size:1.25rem; border-bottom:1px solid #30363d; padding-bottom:.5rem; }
 h2 { font-size:.95rem; color:#79b8ff; margin-top:1.6rem; text-transform:uppercase;
      letter-spacing:.06em; }
 table { border-collapse:collapse; width:100%; margin:.4rem 0 1rem; }
 td,th { border:1px solid #30363d; padding:4px 9px; text-align:left; }
 th { color:#8b949e; font-weight:600; background:#161b22; }
 .grid { display:grid; grid-template-columns:1fr 1fr; gap:0 2rem; }
 .pass { color:#3fb950; font-weight:700; } .fail { color:#f85149; font-weight:700; }
 .on { color:#3fb950; } .off { color:#f85149; } .warn { color:#d29922; }
 .badge { display:inline-block; padding:1px 8px; border:1px solid #30363d;
          border-radius:10px; background:#161b22; }
 .muted { color:#8b949e; } svg { background:#161b22; border:1px solid #30363d; }
 footer { color:#484f58; font-size:.8rem; margin-top:2rem; border-top:1px solid #30363d;
          padding-top:.6rem; }
"""

PLAN_ITEMS = [
    ("Risk engine (sizing, caps, circuit breakers)", "done"),
    ("Data pipeline: Binance klines + funding", "done"),
    ("Macro inputs: FRED DXY/real yields, stablecoin flows", "done"),
    ("Backtest harness + pre-registered grid gate", "done"),
    ("Regime engine", "done"),
    ("Daily signal generator + cockpit", "done"),
    ("Funding-carry monitor", "done"),
    ("Railgun event study (code + pre-registered events)", "done"),
    ("Hypothesis log + risk policy", "done"),
    ("Paper-trading ledger + cost reconciliation", "done"),
    ("Real-data backtest: H1 verdict recorded (FAIL as registered)", "done"),
    ("Carry hypothesis H3: PASS on real funding (+7.3%/yr net)", "done"),
    ("H1b confirmation backtest: GATE PASS (Sharpe 1.26/1.10, maxDD -14.6%)", "done"),
    ("Railgun H2: REJECTED & CLOSED across all 3 tests (U1/U2/U3)", "done"),
    ("4 clean weeks of paper trading (--config h1b daily)", "pending"),
    ("Go/no-go memo for live capital", "pending"),
    ("Execution layer built (dry/testnet/live, risk-checked)", "done"),
    ("Testnet validation, then live at 10% size (after GO)", "gated"),
]


def _fmt(v, pct=False):
    if v is None:
        return "&mdash;"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.2%}" if pct else f"{v:.3f}"
    return str(v)


def _kv_table(d: dict, pct_keys=()) -> str:
    rows = "".join(
        f"<tr><th>{k}</th><td>{_fmt(v, k in pct_keys)}</td></tr>" for k, v in d.items()
    )
    return f"<table>{rows}</table>"


def _records_table(records: list[dict]) -> str:
    if not records:
        return "<p class='muted'>no data yet</p>"
    cols = list(records[0].keys())
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{_fmt(r.get(c))}</td>" for c in cols) + "</tr>"
        for r in records
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def _sparkline(values: list[float], width=640, height=110) -> str:
    if len(values) < 2:
        return "<p class='muted'>not enough history for an equity curve yet</p>"
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pts = " ".join(
        f"{i * width / (len(values) - 1):.1f},{height - 6 - (v - lo) / span * (height - 12):.1f}"
        for i, v in enumerate(values)
    )
    return (
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
        f"<polyline points='{pts}' fill='none' stroke='#58a6ff' stroke-width='1.6'/></svg>"
        f"<div class='muted'>equity {values[0]:,.0f} &rarr; {values[-1]:,.0f}</div>"
    )


def _signals_table(signals: dict) -> str:
    rows = "".join(
        "<tr><td>{s}</td><td class='{c}'>{sig}</td><td>{w:.2%}</td><td>{p:,.2f}</td></tr>".format(
            s=sym,
            c="on" if v["signal"] else "off",
            sig="LONG" if v["signal"] else "FLAT",
            w=v["target_weight"],
            p=v["close"],
        )
        for sym, v in signals.items()
    )
    return (
        "<table><tr><th>Symbol</th><th>Signal</th><th>Target weight</th>"
        f"<th>Close</th></tr>{rows}</table>"
    )


def _plan_section() -> str:
    icon = {"done": "&#10003;", "pending": "&#9203;", "gated": "&#128274;"}
    cls = {"done": "on", "pending": "warn", "gated": "muted"}
    rows = "".join(
        f"<tr><td class='{cls[s]}'>{icon[s]}</td><td>{name}</td></tr>"
        for name, s in PLAN_ITEMS
    )
    return f"<table>{rows}</table>"


def load_hypothesis_log() -> list[dict]:
    if HYPOTHESIS_LOG.exists():
        return json.loads(HYPOTHESIS_LOG.read_text())
    return []


def build_cockpit(
    regime: dict,
    signals: dict,
    carry: dict,
    risk: dict,
    paper: dict | None = None,
    equity_history: list[float] | None = None,
    backtest: dict | None = None,
    event_study: dict | None = None,
    regime_tests: list | None = None,
    reconciliation: dict | None = None,
    data_mode: str = "synthetic",
    out_dir: Path = OUT_DIR,
) -> Path:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode_badge = (
        "<span class='badge warn'>SYNTHETIC DATA &mdash; pipeline demo, run "
        "fetch_data.py for the real thing</span>"
        if data_mode == "synthetic"
        else "<span class='badge on'>REAL DATA</span>"
    )

    parts = [
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>Trading Cockpit</title><style>{CSS}</style></head><body>",
        f"<h1>Two-Sleeve System &mdash; Cockpit</h1>"
        f"<p>Generated {generated} &nbsp; {mode_badge} &nbsp; "
        f"<b>No live orders are placed by this system.</b></p>",
        "<div class='grid'><div>",
        "<h2>Regime</h2>",
        _kv_table(regime),
        "<h2>Sleeve A &mdash; trend signals</h2>",
        _signals_table(signals),
        "<h2>Sleeve B &mdash; funding carry</h2>",
        _kv_table(carry, pct_keys=("trailing_7d_funding_annualized",)),
        "</div><div>",
        "<h2>Risk limits</h2>",
        _kv_table(risk),
    ]
    if paper:
        parts += ["<h2>Paper account</h2>", _kv_table(paper, pct_keys=("drawdown",))]
    if equity_history:
        parts += ["<h2>Equity curve (paper)</h2>", _sparkline(equity_history)]
    parts.append("</div></div>")

    if backtest:
        verdict = backtest.get("pass")
        v_html = (
            f"<span class='{'pass' if verdict else 'fail'}'>"
            f"{'PASS' if verdict else 'FAIL'}</span>"
        )
        parts += [
            f"<h2>Backtest &mdash; pre-registered grid gate: {v_html}</h2>",
            "<p class='muted'>Gate: return &gt; 0, Sharpe &gt; 0.7, maxDD &lt; 35% "
            "across ALL lookbacks. Fixed before results were seen; does not move.</p>",
            _records_table(backtest.get("grid", [])),
            "<h2>Walk-forward (2-year windows)</h2>",
            _records_table(backtest.get("walk_forward", [])),
        ]
    if event_study:
        rows = [
            {"window": k, **v} for k, v in event_study.get("windows", {}).items()
        ]
        parts += [
            "<h2>Railgun / privacy event study (U3)</h2>",
            _records_table(rows),
            f"<p><b>Verdict:</b> {event_study.get('verdict', '')}</p>",
        ]
    if regime_tests:
        parts += [
            "<h2>Railgun / privacy regime tests (U1 / U2)</h2>",
            "<p class='muted'>Mean beta-adjusted abnormal return inside the "
            "uncertainty regime vs outside it (difference-in-differences). "
            "Positive diff = privacy outperforms in the regime.</p>",
            _records_table(regime_tests),
        ]
        for t in regime_tests:
            parts.append(f"<p><b>{t['test']}:</b> {t['verdict']}</p>")
    if reconciliation:
        parts += ["<h2>Cost reconciliation</h2>", _kv_table(reconciliation)]

    log = load_hypothesis_log()
    if log:
        parts += ["<h2>Hypothesis log</h2>", _records_table(log)]
    parts += ["<h2>30-day plan progress</h2>", _plan_section()]
    parts.append(
        "<footer>Pre-registered rules: docs/trading-system-analysis.md &sect;5&ndash;8 "
        "&middot; risk policy: RISK_POLICY.md &middot; overrides target: zero.</footer>"
        "</body></html>"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "cockpit.html"
    path.write_text("".join(parts))
    return path
