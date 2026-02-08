"use client";

import { useMonthlyBudget, useCategorySpending } from "@/lib/hooks/useApi";
import { formatEUR, CATEGORY_LABELS, CHART_COLORS } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function BudgetPage() {
  const { data: monthly } = useMonthlyBudget(12);
  const { data: categories } = useCategorySpending(3);

  return (
    <div className="space-y-6">
      <p className="text-[13px] font-medium" style={{ color: "var(--text-5)" }}>Budget</p>

      {/* Revenue vs Expenses chart */}
      <div className="card p-6">
        <h3 className="text-[13px] font-medium mb-5" style={{ color: "var(--text-4)" }}>
          Revenus vs Depenses
        </h3>
        {monthly && monthly.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={[...monthly].reverse()} barGap={2}>
              <XAxis
                dataKey="month"
                tick={{ fontSize: 11, fill: "var(--text-5)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                tick={{ fontSize: 11, fill: "var(--text-5)" }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-3)",
                  border: "1px solid var(--border-1)",
                  borderRadius: 8,
                  color: "var(--text-1)",
                  fontSize: 13,
                }}
                formatter={(v: number) => formatEUR(v)}
                cursor={{ fill: "var(--bg-hover)" }}
              />
              <Bar dataKey="income" name="Revenus" fill="var(--green)" opacity={0.8} radius={[3, 3, 0, 0]} />
              <Bar dataKey="expenses" name="Depenses" fill="var(--red)" opacity={0.5} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-5)" }}>Aucune donnee</p>
        )}
      </div>

      {/* Top categories */}
      <div className="card p-6">
        <h3 className="text-[13px] font-medium mb-5" style={{ color: "var(--text-4)" }}>
          Top categories (3 mois)
        </h3>
        {categories && categories.length > 0 ? (
          <div className="space-y-4">
            {categories.map((c, i) => {
              const maxTotal = categories[0]?.total ?? 1;
              const pct = (c.total / maxTotal) * 100;
              return (
                <div key={c.category}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                      />
                      <span className="text-[13px]" style={{ color: "var(--text-3)" }}>
                        {CATEGORY_LABELS[c.category] || c.category}
                      </span>
                    </div>
                    <span className="tnum text-[13px] font-medium" style={{ color: "var(--text-1)" }}>
                      {formatEUR(c.total)}
                    </span>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                        opacity: 0.6,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-[13px]" style={{ color: "var(--text-5)" }}>Aucune donnee</p>
        )}
      </div>
    </div>
  );
}
