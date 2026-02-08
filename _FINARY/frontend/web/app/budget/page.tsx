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
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";

export default function BudgetPage() {
  const { data: monthly } = useMonthlyBudget(12);
  const { data: categories } = useCategorySpending(3);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Budget</h2>

      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-500 mb-4">
          Revenus vs Dépenses
        </h3>
        {monthly && (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={[...monthly].reverse()}>
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => formatEUR(v)} />
              <Legend />
              <Bar
                dataKey="income"
                name="Revenus"
                fill={CHART_COLORS[0]}
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="expenses"
                name="Dépenses"
                fill={CHART_COLORS[3]}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-500 mb-4">
          Top catégories (3 mois)
        </h3>
        {categories && (
          <div className="space-y-2">
            {categories.map((c, i) => (
              <div key={c.category} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                  />
                  <span>{CATEGORY_LABELS[c.category] || c.category}</span>
                </div>
                <span className="font-medium">{formatEUR(c.total)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
