"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
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
  cash: "Liquidités",
  savings: "Épargne",
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
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <h3 className="text-sm font-medium text-gray-500 mb-4">
        Répartition par classe
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            dataKey="value"
            label={({ name, value }) =>
              `${name} ${((value / total) * 100).toFixed(0)}%`
            }
          >
            {data.map((_, i) => (
              <Cell
                key={i}
                fill={CHART_COLORS[i % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip formatter={(v: number) => formatEUR(v)} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
