"use client";
import { RadialBar, RadialBarChart, PolarAngleAxis } from "recharts";

// Semicircular gauge. `frac` in [0,1] fills the arc; center shows `value`.
export function Gauge({
  frac,
  value,
  sub,
  label,
  color,
}: {
  frac: number;
  value: string;
  sub: string;
  label: string;
  color: string;
}) {
  const data = [{ name: label, value: Math.max(0, Math.min(1, frac)) * 100 }];
  return (
    <div className="card" style={{ textAlign: "center" }}>
      <div style={{ position: "relative", height: 120 }}>
        <RadialBarChart
          width={200}
          height={160}
          cx={100}
          cy={110}
          innerRadius={62}
          outerRadius={84}
          barSize={14}
          data={data}
          startAngle={180}
          endAngle={0}
          style={{ margin: "0 auto" }}
        >
          <PolarAngleAxis
            type="number"
            domain={[0, 100]}
            angleAxisId={0}
            tick={false}
          />
          <RadialBar
            background={{ fill: "#222a39" }}
            dataKey="value"
            cornerRadius={8}
            fill={color}
          />
        </RadialBarChart>
        <div
          style={{
            position: "absolute",
            top: 64,
            left: 0,
            right: 0,
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
          <div className="muted" style={{ fontSize: 11 }}>
            {sub}
          </div>
        </div>
      </div>
      <div className="kpi-l">{label}</div>
    </div>
  );
}
