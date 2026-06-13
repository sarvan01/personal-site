"use client";
import { useEffect, useState } from "react";
import type { Status } from "@/lib/types";
import { Gauge } from "@/components/Gauge";
import { EquityChart } from "@/components/EquityChart";

export default function Page() {
  const [s, setS] = useState<Status | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("/status.json", { cache: "no-store" })
      .then((r) => r.json())
      .then(setS)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="wrap">Failed to load status.json: {err}</div>;
  if (!s) return <div className="wrap muted">Loading…</div>;

  const mult = s.regime?.exposure_multiplier ?? 0;
  const dd = s.paper?.drawdown ?? 0;
  const fund = s.carry?.trailing_7d_funding_annualized ?? 0;
  const gate = s.backtest?.pass ?? s.backtest_gate === "PASS";
  const ddCol = Math.abs(dd) < 0.1 ? "#2ecc71" : Math.abs(dd) < 0.15 ? "#f0b400" : "#ff5470";
  const fundIn = s.carry?.signal === "IN";

  return (
    <div className="wrap">
      <div className="head">
        <div>
          <h1>Two-Sleeve System — Cockpit</h1>
          <div className="sub">
            Generated {s.generated_utc ?? "—"} · No live orders are placed by this system.
          </div>
        </div>
        <span className={`badge ${s.data_mode === "real" ? "on" : "warn"}`}>
          {s.data_mode === "real" ? "REAL DATA" : "SYNTHETIC DATA"}
        </span>
      </div>

      {s.stale_data_warnings && s.stale_data_warnings.length > 0 && (
        <div className="banner">
          <b>⚠ STALE DATA</b> — re-run fetch_data.py before trusting today&apos;s run.
          <ul>
            {s.stale_data_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <h2>At a glance</h2>
      <div className="grid kpis">
        <Kpi label="Paper equity" value={`$${(s.paper?.equity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`} sub={`peak $${(s.paper?.peak_equity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
        <Kpi label="Drawdown" value={`${(dd * 100).toFixed(1)}%`} sub="halve -10% / flat -15%" tone={Math.abs(dd) >= 0.15 ? "bad" : Math.abs(dd) >= 0.1 ? "warnv" : "good"} />
        <Kpi label="Paper days" value={`${s.paper?.days_recorded ?? 0}`} sub="need ≥ 20 clean" tone={(s.paper?.days_recorded ?? 0) >= 20 ? "good" : ""} />
        <Kpi label="Regime" value={(s.regime?.state ?? "—").replace(/_/g, " ")} sub={`exposure ×${mult.toFixed(2)}`} />
        <Kpi label="Carry" value={s.carry?.signal ?? "—"} sub="funding sleeve" tone={fundIn ? "good" : ""} />
        <Kpi label="Backtest gate" value={gate ? "PASS" : "FAIL"} sub="pre-registered" tone={gate ? "good" : "bad"} />
      </div>

      <h2>Gauges</h2>
      <div className="grid gauges">
        <Gauge frac={mult} value={mult.toFixed(2)} sub={s.regime?.state ?? ""} label="Regime exposure" color="#4c8dff" />
        <Gauge frac={Math.min(Math.abs(dd) / 0.15, 1)} value={`${(dd * 100).toFixed(1)}%`} sub="breaker -15%" label="Drawdown vs breaker" color={ddCol} />
        <Gauge frac={Math.min(Math.max(fund, 0) / 0.2, 1)} value={`${(fund * 100).toFixed(1)}%`} sub={s.carry?.signal ?? ""} label="Funding 7d (ann.)" color={fundIn ? "#2ecc71" : "#8b97a8"} />
        <Gauge frac={gate ? 1 : 0} value={gate ? "PASS" : "FAIL"} sub="grid gate" label="Backtest" color={gate ? "#2ecc71" : "#ff5470"} />
      </div>

      <h2>Equity curve (paper)</h2>
      <EquityChart values={s.equity_history ?? []} />

      <h2>Sleeve A — trend signals</h2>
      <div className="grid cards">
        {Object.entries(s.signals ?? {}).map(([sym, v]) => (
          <div className="card" key={sym}>
            <div className="srow">
              <b>{sym}</b>
              <span className={`pill ${v.signal ? "on" : "off"}`}>{v.signal ? "LONG" : "FLAT"}</span>
            </div>
            <div className="muted mono">${v.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
            <div className="bar">
              <span style={{ width: `${Math.min(Math.max(v.target_weight / 0.25, 0), 1) * 100}%` }} />
            </div>
            <div className="muted mono">target {(v.target_weight * 100).toFixed(1)}%</div>
          </div>
        ))}
      </div>

      {s.backtest?.grid && (
        <>
          <h2>Backtest grid</h2>
          <div className="card">
            <Table rows={s.backtest.grid} />
          </div>
        </>
      )}

      <footer className="muted" style={{ marginTop: 28, fontSize: 11.5 }}>
        Pre-registered rules: docs/trading-system-analysis.md §5–8 · risk policy: RISK_POLICY.md
      </footer>
    </div>
  );
}

function Kpi({ label, value, sub, tone = "" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="card">
      <div className={`kpi-v ${tone}`}>{value}</div>
      <div className="kpi-l">{label}</div>
      {sub && <div className="kpi-s">{sub}</div>}
    </div>
  );
}

function Table({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <div className="muted">no data</div>;
  const cols = Object.keys(rows[0]);
  return (
    <table>
      <thead>
        <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {cols.map((c) => (
              <td className="mono" key={c}>
                {typeof r[c] === "number" ? (r[c] as number).toFixed(3) : String(r[c])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
