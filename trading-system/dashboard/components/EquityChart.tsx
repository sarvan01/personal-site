"use client";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";

export function EquityChart({ values }: { values: number[] }) {
  if (!values || values.length < 2) {
    return (
      <div className="card muted">
        building paper history — the equity curve appears after a few days
      </div>
    );
  }
  const data = values.map((v, i) => ({ i, equity: v }));
  const up = values[values.length - 1] >= values[0];
  const color = up ? "#2ecc71" : "#ff5470";
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  return (
    <div className="card">
      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
          <defs>
            <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis domain={[lo, hi]} hide />
          <Tooltip
            contentStyle={{ background: "#131722", border: "1px solid #222a39" }}
            labelFormatter={() => ""}
            formatter={(v: number) => [`$${v.toLocaleString()}`, "equity"]}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={color}
            strokeWidth={2}
            fill="url(#eq)"
          />
        </AreaChart>
      </ResponsiveContainer>
      <div className="muted mono">
        {values[0].toLocaleString()} &rarr;{" "}
        {values[values.length - 1].toLocaleString()} (
        {(((values[values.length - 1] - values[0]) / values[0]) * 100).toFixed(2)}
        %)
      </div>
    </div>
  );
}
