"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { formatEUR, CHART_COLORS } from "@/lib/utils";

interface Props {
  breakdown: {
    cash: number;
    savings: number;
    investments: number;
    real_estate: number;
  };
}

const LABELS: Record<string, string> = {
  cash: "Liquidites",
  savings: "Epargne",
  investments: "Investissements",
  real_estate: "Immobilier",
};

export function BreakdownDonut({ breakdown }: Props) {
  const data = Object.entries(breakdown)
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({
      name: LABELS[key] || key,
      value,
    }));

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="card p-6">
      <h3 className="text-[13px] font-medium mb-5" style={{ color: "var(--text-4)" }}>
        Repartition par classe
      </h3>
      <div className="flex items-center gap-8">
        <div className="w-[140px] h-[140px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={45}
                outerRadius={65}
                dataKey="value"
                stroke="none"
                startAngle={90}
                endAngle={-270}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-3">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <span className="text-[13px]" style={{ color: "var(--text-3)" }}>{d.name}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="tnum text-[13px] font-medium" style={{ color: "var(--text-1)" }}>
                  {formatEUR(d.value)}
                </span>
                <span className="tnum text-[11px] w-10 text-right" style={{ color: "var(--text-5)" }}>
                  {((d.value / total) * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
