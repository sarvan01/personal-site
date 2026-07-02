"""The cockpit: one self-contained, premium HTML dashboard that aggregates
everything — regime, signals, carry, risk and breaker state, paper equity,
backtest verdict, walk-forward, (archived) Railgun tests, cost reconciliation,
the hypothesis log, and plan progress.

Pure inline SVG + CSS: no web server, no Node, no external assets. Works
offline; open out/cockpit.html in any browser. Renders from plain dicts, so
it behaves identically on synthetic or real data.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .milkroad import INDICATOR_ORDER

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
HYPOTHESIS_LOG = ROOT / "research" / "hypothesis_log.json"

# Palette
BG = "#0b0e14"
CARD = "#131722"
LINE = "#222a39"
INK = "#e6edf3"
MUTE = "#8b97a8"
BLUE = "#4c8dff"
GREEN = "#2ecc71"
AMBER = "#f0b400"
RED = "#ff5470"

CSS = f"""
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
 background:{BG};color:{INK};margin:0;padding:24px;line-height:1.45}}
.wrap{{max-width:1180px;margin:0 auto}}
.head{{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;
 border-bottom:1px solid {LINE};padding-bottom:14px;margin-bottom:18px}}
h1{{font-size:20px;margin:0;font-weight:700;letter-spacing:-.01em}}
.sub{{color:{MUTE};font-size:12.5px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600;
 border:1px solid {LINE};background:{CARD}}}
.badge.on{{color:{GREEN};border-color:#1c6b3f}} .badge.warn{{color:{AMBER};border-color:#6b5510}}
.mono{{font-variant-numeric:tabular-nums;font-feature-settings:'tnum'}}
h2{{font-size:12px;color:{MUTE};text-transform:uppercase;letter-spacing:.08em;margin:26px 0 10px;font-weight:600}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.kpi{{background:{CARD};border:1px solid {LINE};border-radius:12px;padding:14px 16px}}
.kpi-v{{font-size:22px;font-weight:700;letter-spacing:-.02em}}
.kpi-l{{color:{MUTE};font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-top:2px}}
.kpi-s{{color:{MUTE};font-size:12px;margin-top:4px}}
.kpi.good .kpi-v{{color:{GREEN}}} .kpi.bad .kpi-v{{color:{RED}}} .kpi.warnv .kpi-v{{color:{AMBER}}}
.gauges{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}
.gcard{{background:{CARD};border:1px solid {LINE};border-radius:12px;padding:10px;text-align:center}}
.glabel{{color:{MUTE};font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-top:2px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}
.scard{{background:{CARD};border:1px solid {LINE};border-radius:12px;padding:14px}}
.srow{{display:flex;justify-content:space-between;align-items:center}}
.pill{{font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px}}
.pill.on{{background:#10331f;color:{GREEN}}} .pill.off{{background:#33161c;color:{RED}}}
.bar{{height:6px;background:{LINE};border-radius:6px;margin:10px 0 6px;overflow:hidden}}
.bar>span{{display:block;height:100%;background:{BLUE};border-radius:6px}}
.panel{{background:{CARD};border:1px solid {LINE};border-radius:12px;padding:6px 16px 14px;margin-top:8px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border-bottom:1px solid {LINE};padding:7px 8px;text-align:left}}
th{{color:{MUTE};font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
tr:last-child td{{border-bottom:none}}
.muted{{color:{MUTE}}} .pass{{color:{GREEN};font-weight:700}} .fail{{color:{RED};font-weight:700}}
.gate{{display:inline-block;padding:3px 12px;border-radius:8px;font-weight:700;font-size:13px}}
.gate.pass{{background:#10331f;color:{GREEN}}} .gate.fail{{background:#33161c;color:{RED}}}
.banner{{border:1px solid {RED};background:#2a1117;color:#ffc2cd;padding:10px 14px;border-radius:10px;margin:6px 0 2px}}
.checklist{{list-style:none;padding:0;margin:0;columns:2;column-gap:28px}}
.checklist li{{padding:3px 0;font-size:13px;break-inside:avoid}}
.ic-done{{color:{GREEN}}} .ic-pending{{color:{AMBER}}} .ic-gated{{color:{MUTE}}}
footer{{color:#5a6473;font-size:11.5px;margin-top:28px;border-top:1px solid {LINE};padding-top:12px}}
@media(max-width:560px){{.checklist{{columns:1}}}}
"""

PLAN_ITEMS = [
    ("Risk engine (sizing, caps, circuit breakers)", "done"),
    ("Data pipeline: Binance klines + funding", "done"),
    ("Backtest harness + pre-registered grid gate", "done"),
    ("Regime engine", "done"),
    ("Daily signal generator + cockpit", "done"),
    ("Funding-carry monitor", "done"),
    ("Hypothesis log + risk policy", "done"),
    ("Paper-trading ledger + cost reconciliation", "done"),
    ("H1 verdict recorded (FAIL as registered)", "done"),
    ("Carry H3: PASS on real funding (+7.3%/yr net)", "done"),
    ("H1b confirmation backtest: GATE PASS (Sharpe 1.26/1.10)", "done"),
    ("Railgun H2: REJECTED & CLOSED (U1/U2/U3)", "done"),
    ("Execution layer built (dry/testnet/live, risk-checked)", "done"),
    ("Stale-data detection", "done"),
    ("4 clean weeks of paper trading (--config h1b daily)", "pending"),
    ("Go/no-go memo for live capital", "pending"),
    ("Testnet validation, then live at 10% size (after GO)", "gated"),
]


# ----------------------------------------------------------------------------
# small formatters / tables (used by the detail panels)
# ----------------------------------------------------------------------------
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
        f"<tr><th>{k}</th><td class='mono'>{_fmt(v, k in pct_keys)}</td></tr>"
        for k, v in d.items()
    )
    return f"<table>{rows}</table>"


def _records_table(records: list[dict]) -> str:
    if not records:
        return "<p class='muted'>no data yet</p>"
    cols = list(records[0].keys())
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td class='mono'>{_fmt(r.get(c))}</td>" for c in cols) + "</tr>"
        for r in records
    )
    return f"<table><tr>{head}</tr>{body}</table>"


# ----------------------------------------------------------------------------
# premium widgets (inline SVG)
# ----------------------------------------------------------------------------
def _arc_gauge(frac: float, center: str, sub: str, label: str, color: str) -> str:
    frac = max(0.0, min(1.0, frac))
    r, cx, cy, sw = 64, 90, 86, 13

    def pt(ang):
        return cx + r * math.cos(ang), cy - r * math.sin(ang)

    x0, y0 = pt(math.pi)
    xb, yb = pt(0.0)
    xv, yv = pt(math.pi - math.pi * frac)
    bg = (f"<path d='M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {xb:.1f},{yb:.1f}' fill='none' "
          f"stroke='{LINE}' stroke-width='{sw}' stroke-linecap='round'/>")
    val = (f"<path d='M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {xv:.1f},{yv:.1f}' fill='none' "
           f"stroke='{color}' stroke-width='{sw}' stroke-linecap='round'/>")
    txt = (f"<text x='{cx}' y='{cy-4}' text-anchor='middle' fill='{INK}' font-size='23' "
           f"font-weight='700'>{center}</text>"
           f"<text x='{cx}' y='{cy+15}' text-anchor='middle' fill='{MUTE}' font-size='11'>{sub}</text>")
    return (f"<div class='gcard'><svg viewBox='0 0 180 104' width='100%' height='104'>"
            f"{bg}{val}{txt}</svg><div class='glabel'>{label}</div></div>")


def _area_chart(values: list[float], width: int = 1140, height: int = 170) -> str:
    if not values or len(values) < 2:
        return "<div class='panel'><p class='muted'>building paper history — the equity curve appears after a few days</p></div>"
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(values)

    def X(i):
        return i * width / (n - 1)

    def Y(v):
        return height - 10 - (v - lo) / span * (height - 28)

    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(values))
    up = values[-1] >= values[0]
    col = GREEN if up else RED
    area = f"M{X(0):.1f},{height} L" + line.replace(" ", " L") + f" L{X(n-1):.1f},{height} Z"
    chg = values[-1] / values[0] - 1.0
    return (
        f"<div class='panel'><svg viewBox='0 0 {width} {height}' width='100%' height='{height}' "
        f"preserveAspectRatio='none'>"
        f"<defs><linearGradient id='eq' x1='0' y1='0' x2='0' y2='1'>"
        f"<stop offset='0' stop-color='{col}' stop-opacity='0.28'/>"
        f"<stop offset='1' stop-color='{col}' stop-opacity='0'/></linearGradient></defs>"
        f"<path d='{area}' fill='url(#eq)'/>"
        f"<polyline points='{line}' fill='none' stroke='{col}' stroke-width='2'/></svg>"
        f"<div class='muted mono'>{values[0]:,.0f} &rarr; {values[-1]:,.0f} "
        f"({chg:+.2%})</div></div>"
    )


def _kpi(label: str, value: str, sub: str = "", tone: str = "") -> str:
    return (f"<div class='kpi {tone}'><div class='kpi-v mono'>{value}</div>"
            f"<div class='kpi-l'>{label}</div><div class='kpi-s'>{sub}</div></div>")


def _signal_cards(signals: dict) -> str:
    cards = []
    for sym, v in signals.items():
        on = v["signal"]
        w = v["target_weight"]
        pct = min(max(w / 0.25, 0.0), 1.0) * 100
        cards.append(
            f"<div class='scard'><div class='srow'><b>{sym}</b>"
            f"<span class='pill {'on' if on else 'off'}'>{'LONG' if on else 'FLAT'}</span></div>"
            f"<div class='muted mono'>${v['close']:,.2f}</div>"
            f"<div class='bar'><span style='width:{pct:.0f}%'></span></div>"
            f"<div class='muted mono'>target {w:.1%}</div></div>"
        )
    return "<div class='cards'>" + "".join(cards) + "</div>"


def _milkroad_panel(m: dict) -> str:
    """Milk Road CONTEXT feed — indicators + latest trades. Explicitly not a
    trading signal; neutral colouring so it never reads as buy/sell guidance."""
    inds = m.get("indicators", {}) or {}
    meters = []
    for key in INDICATOR_ORDER:
        if key not in inds:
            continue
        ind = inds[key]
        v = ind.get("value")
        # Indicators may use any range (e.g. Milk Road's Macro Index runs
        # roughly -3..+3, not 0-100) -- normalize using optional min/max,
        # defaulting to 0-100 for indicators that already are (fear_greed).
        lo, hi = float(ind.get("min", 0)), float(ind.get("max", 100))
        span = (hi - lo) or 1.0
        pct = max(0.0, min(100.0, ((float(v) - lo) / span * 100.0) if v is not None else 0.0))
        meters.append(
            f"<div class='card'><div class='kpi-v mono'>{'—' if v is None else v}"
            f"<span class='muted' style='font-size:12px'> {ind.get('label','')}</span></div>"
            f"<div class='bar'><span style='width:{pct:.0f}%'></span></div>"
            f"<div class='kpi-l'>{key.replace('_',' ')}</div>"
            f"<div class='kpi-s'>as of {ind.get('as_of','—')}</div></div>"
        )
    tone = {"BUY": "on", "ADD": "on", "SELL": "off", "TRIM": "off"}
    trade_list = (m.get("trades") or [])[:12]
    # Optional richer columns (Milk Road's Analyst Trade Log has these; plain
    # manual/Discord entries won't) -- only add a column if any trade has it.
    has_analyst = any(t.get("analyst") for t in trade_list)
    has_perf = any(t.get("perf_pct") is not None for t in trade_list)
    rows = []
    for t in trade_list:
        act = str(t.get("action", "")).upper()
        cls = tone.get(act, "")
        pill = (f"<span class='pill {cls}'>{act}</span>" if cls
                else f"<span class='pill' style='background:#1c2436;color:#8b97a8'>{act}</span>")
        note = t.get("note", "")
        cells = [f"<td class='mono'>{t.get('date','')}</td>"]
        if has_analyst:
            cells.append(f"<td>{t.get('analyst','')}</td>")
        cells.append(f"<td>{pill}</td><td><b>{t.get('asset','')}</b></td>")
        if has_perf:
            p = t.get("perf_pct")
            pcls = "pass" if isinstance(p, (int, float)) and p > 0 else \
                   "fail" if isinstance(p, (int, float)) and p < 0 else "muted"
            cells.append(f"<td class='mono {pcls}'>{f'{p:+.1f}%' if p is not None else '—'}</td>")
        cells.append(f"<td class='muted'>{note}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    head = (
        "<th>date</th>" + ("<th>analyst</th>" if has_analyst else "")
        + "<th>action</th><th>asset</th>" + ("<th>perf</th>" if has_perf else "")
        + "<th>note</th>"
    )
    trades_html = (
        f"<table><tr>{head}</tr>{''.join(rows)}</table>"
        if rows else "<p class='muted'>no trades in feed</p>"
    )
    updated = m.get("updated_utc", "—")
    return (
        "<h2>Milk Road — context feed</h2>"
        f"<div class='banner' style='border-color:{LINE};background:{CARD};color:{MUTE}'>"
        "<b>CONTEXT ONLY — not a trading signal.</b> Informational; it does not "
        f"drive the strategy or the paper account. Updated {updated}.</div>"
        f"<div class='grid gauges'>{''.join(meters)}</div>"
        f"<div class='panel'>{trades_html}</div>"
    )


def _plan_section() -> str:
    icon = {"done": "&#10003;", "pending": "&#9203;", "gated": "&#128274;"}
    items = "".join(
        f"<li><span class='ic-{s}'>{icon[s]}</span> {name}</li>" for name, s in PLAN_ITEMS
    )
    return f"<ul class='checklist'>{items}</ul>"


def load_hypothesis_log() -> list[dict]:
    if HYPOTHESIS_LOG.exists():
        return json.loads(HYPOTHESIS_LOG.read_text())
    return []


# ----------------------------------------------------------------------------
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
    warnings: list | None = None,
    milkroad: dict | None = None,
    out_dir: Path = OUT_DIR,
) -> Path:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    badge = ("<span class='badge warn'>SYNTHETIC DATA</span>" if data_mode == "synthetic"
             else "<span class='badge on'>REAL DATA</span>")

    banner = ""
    if warnings:
        items = "".join(f"<li>{w}</li>" for w in warnings)
        banner = (f"<div class='banner'><b>&#9888; STALE DATA</b> — the cockpit is running "
                  f"on old cached data. Re-run fetch_data.py before trusting today's run."
                  f"<ul>{items}</ul></div>")

    # ---- gauges -------------------------------------------------------------
    mult = float(regime.get("exposure_multiplier", regime.get("multiplier", 0)) or 0)
    g_exposure = _arc_gauge(mult, f"{mult:.2f}", regime.get("state", ""), "Regime exposure", BLUE)

    dd = float(paper.get("drawdown", 0.0)) if paper else 0.0
    dd_frac = min(abs(dd) / 0.15, 1.0)
    dd_col = GREEN if abs(dd) < 0.10 else AMBER if abs(dd) < 0.15 else RED
    g_dd = _arc_gauge(dd_frac, f"{dd:.1%}", "breaker -15%", "Drawdown vs breaker", dd_col)

    fund = float(carry.get("trailing_7d_funding_annualized", 0.0))
    f_in = carry.get("signal") == "IN"
    g_fund = _arc_gauge(min(max(fund, 0) / 0.20, 1.0), f"{fund:.1%}",
                        carry.get("signal", ""), "Funding 7d (ann.)",
                        GREEN if f_in else MUTE)

    gate = bool(backtest.get("pass")) if backtest else None
    gate_frac = 1.0 if gate else 0.0
    g_gate = _arc_gauge(gate_frac, "PASS" if gate else "FAIL", "grid gate",
                        "Backtest", GREEN if gate else RED)

    # ---- KPI tiles ----------------------------------------------------------
    kpis = []
    if paper:
        eq = paper.get("equity", 0.0)
        kpis.append(_kpi("Paper equity", f"${eq:,.0f}", f"peak ${paper.get('peak_equity', 0):,.0f}"))
        kpis.append(_kpi("Drawdown", f"{dd:.1%}",
                         "halve -10% / flat -15%",
                         "bad" if abs(dd) >= 0.15 else "warnv" if abs(dd) >= 0.10 else "good"))
        days = paper.get("days_recorded", 0)
        kpis.append(_kpi("Paper days", f"{days}", "need >= 20 clean",
                         "good" if days >= 20 else ""))
    kpis.append(_kpi("Regime", regime.get("state", "&mdash;").replace("_", " "),
                     f"exposure x{mult:.2f}"))
    kpis.append(_kpi("Carry", carry.get("signal", "&mdash;"),
                     f"hurdle {carry.get('enter_hurdle', 0.10):.0%}",
                     "good" if f_in else ""))
    if backtest is not None:
        kpis.append(_kpi("Backtest gate", "PASS" if gate else "FAIL", "pre-registered",
                         "good" if gate else "bad"))

    # ---- detail panels ------------------------------------------------------
    panels = []
    if backtest:
        g_html = f"<span class='gate {'pass' if gate else 'fail'}'>{'PASS' if gate else 'FAIL'}</span>"
        panels += [
            f"<h2>Backtest — pre-registered grid gate: {g_html}</h2>",
            "<div class='panel'><p class='muted'>Gate: return &gt; 0, Sharpe &gt; 0.7, "
            "maxDD &lt; 35% across ALL lookbacks. Fixed before results were seen.</p>"
            + _records_table(backtest.get("grid", []))
            + "<h2>Walk-forward (2-year windows)</h2>"
            + _records_table(backtest.get("walk_forward", [])) + "</div>",
        ]
    panels += ["<h2>Risk limits</h2>", "<div class='panel'>" + _kv_table(risk) + "</div>"]
    if reconciliation:
        panels += ["<h2>Cost reconciliation</h2>", "<div class='panel'>" + _kv_table(reconciliation) + "</div>"]

    if event_study:
        rows = [{"window": k, **v} for k, v in event_study.get("windows", {}).items()]
        panels += [
            "<h2>Railgun / privacy event study (U3) — archived</h2>",
            "<div class='panel'>" + _records_table(rows)
            + f"<p class='muted'><b>Verdict:</b> {event_study.get('verdict', '')}</p></div>",
        ]
    if regime_tests:
        v = "".join(f"<p class='muted'><b>{t['test']}:</b> {t['verdict']}</p>" for t in regime_tests)
        panels += [
            "<h2>Railgun / privacy regime tests (U1 / U2) — archived</h2>",
            "<div class='panel'>" + _records_table(regime_tests) + v + "</div>",
        ]

    log = load_hypothesis_log()
    if log:
        panels += ["<h2>Hypothesis log</h2>", "<div class='panel'>" + _records_table(log) + "</div>"]
    panels += ["<h2>Plan progress</h2>", "<div class='panel'>" + _plan_section() + "</div>"]

    html = (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Trading Cockpit</title><style>{CSS}</style></head><body><div class='wrap'>"
        f"<div class='head'><div><h1>Two-Sleeve System — Cockpit</h1>"
        f"<div class='sub'>Generated {generated} · <b>No live orders are placed by this system.</b></div></div>"
        f"<div>{badge}</div></div>"
        f"{banner}"
        f"<h2>At a glance</h2><div class='kpis'>{''.join(kpis)}</div>"
        f"<h2>Gauges</h2><div class='gauges'>{g_exposure}{g_dd}{g_fund}{g_gate}</div>"
        f"{_milkroad_panel(milkroad) if milkroad else ''}"
        f"<h2>Equity curve (paper)</h2>{_area_chart(equity_history or [])}"
        f"<h2>Sleeve A — trend signals</h2>{_signal_cards(signals)}"
        f"<h2>Sleeve B — funding carry</h2><div class='panel'>"
        f"{_kv_table(carry, pct_keys=('trailing_7d_funding_annualized',))}</div>"
        + "".join(panels)
        + "<footer>Pre-registered rules: docs/trading-system-analysis.md §5–8 · "
        "risk policy: RISK_POLICY.md · overrides target: zero.</footer>"
        "</div></body></html>"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "cockpit.html"
    path.write_text(html)
    return path
