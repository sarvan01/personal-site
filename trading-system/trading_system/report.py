"""Output layer: daily status as JSON and a single static HTML page
(the 'Home screen' from report section 7 — regime, signals, risk state).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "out"

_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Trading System Status</title>
<style>
 body {{ font-family: ui-monospace, monospace; background: #111; color: #ddd;
        max-width: 720px; margin: 2rem auto; padding: 0 1rem; }}
 h1 {{ font-size: 1.2rem; }} h2 {{ font-size: 1rem; color: #9cf; }}
 table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
 td, th {{ border: 1px solid #333; padding: 4px 8px; text-align: left; }}
 .on {{ color: #6f6; }} .off {{ color: #f66; }}
 footer {{ color: #666; font-size: 0.8rem; margin-top: 2rem; }}
</style></head><body>
<h1>Two-Sleeve System &mdash; Daily Status</h1>
<p>Generated {generated} UTC. <b>No live orders are placed by this system.</b></p>
<h2>Regime</h2><table>{regime_rows}</table>
<h2>Sleeve A &mdash; Trend signals</h2><table>
<tr><th>Symbol</th><th>Signal</th><th>Target weight</th></tr>{signal_rows}</table>
<h2>Sleeve B &mdash; Funding carry</h2><table>{carry_rows}</table>
<h2>Risk state</h2><table>{risk_rows}</table>
<footer>Pre-registered rules: docs/trading-system-analysis.md &sect;5.
Overrides target: zero.</footer>
</body></html>
"""


def _rows(d: dict) -> str:
    return "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in d.items())


def write_status(
    regime: dict, signals: dict, carry: dict, risk: dict, out_dir: Path = OUT_DIR
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    status = {
        "generated_utc": generated,
        "regime": regime,
        "trend_signals": signals,
        "carry": carry,
        "risk": risk,
    }
    json_path = out_dir / "status.json"
    json_path.write_text(json.dumps(status, indent=2, default=str))

    signal_rows = "".join(
        "<tr><td>{s}</td><td class='{c}'>{sig}</td><td>{w:.1%}</td></tr>".format(
            s=sym,
            c="on" if v["signal"] else "off",
            sig="LONG" if v["signal"] else "FLAT",
            w=v["target_weight"],
        )
        for sym, v in signals.items()
    )
    html_path = out_dir / "status.html"
    html_path.write_text(
        _HTML.format(
            generated=generated,
            regime_rows=_rows(regime),
            signal_rows=signal_rows,
            carry_rows=_rows(carry),
            risk_rows=_rows(risk),
        )
    )
    return json_path, html_path
