"use client";

import { useMemo } from "react";
import { useMonthlyBudget, useCategorySpending } from "@/lib/hooks/useApi";
import { formatEUR, CATEGORY_LABELS, CHART_COLORS } from "@/lib/utils";
import { BudgetChart } from "@/components/charts/BudgetChart";
import {
  generateMonthlyBudget,
  generateCategorySpending,
} from "@/lib/fixtures";

export default function BudgetPage() {
  const { data: apiMonthly } = useMonthlyBudget(12);
  const { data: apiCategories } = useCategorySpending(3);

  const monthly = useMemo(() => {
    if (apiMonthly && apiMonthly.length > 0) return apiMonthly;
    return generateMonthlyBudget(12);
  }, [apiMonthly]);

  const categories = useMemo(() => {
    if (apiCategories && apiCategories.length > 0) return apiCategories;
    return generateCategorySpending();
  }, [apiCategories]);

  // Compute totals for current month
  const lastMonth = monthly[monthly.length - 1];
  const savingsRate = lastMonth
    ? ((lastMonth.income - lastMonth.expenses) / lastMonth.income) * 100
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-2" style={{ color: "var(--text-5)" }}>
          Budget
        </p>
        {lastMonth && (
          <div className="flex items-center gap-6">
            <div>
              <p className="tnum text-[32px] font-extralight tracking-tight leading-none" style={{ color: "var(--text-1)" }}>
                {formatEUR(lastMonth.income - lastMonth.expenses)}
              </p>
              <p className="text-[11px] mt-1" style={{ color: "var(--text-5)" }}>
                epargne ce mois
              </p>
            </div>
            <span
              className="tnum text-[12px] font-medium px-2.5 py-1 rounded"
              style={{
                background: savingsRate >= 0 ? "var(--green-bg)" : "var(--red-bg)",
                color: savingsRate >= 0 ? "var(--green)" : "var(--red)",
              }}
            >
              {savingsRate.toFixed(0)}% du revenu
            </span>
          </div>
        )}
      </div>

      {/* Revenue vs Expenses chart */}
      <div className="card p-6">
        <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-5" style={{ color: "var(--text-5)" }}>
          Revenus vs Depenses
        </h3>
        <BudgetChart data={monthly} />
      </div>

      {/* KPI cards */}
      {lastMonth && (
        <div className="grid grid-cols-3 gap-3">
          <div className="card px-5 py-4">
            <p className="text-[10px] font-medium tracking-[0.06em] uppercase" style={{ color: "var(--text-6)" }}>
              Revenus
            </p>
            <p className="tnum text-lg font-semibold mt-1.5" style={{ color: "var(--green)" }}>
              {formatEUR(lastMonth.income)}
            </p>
          </div>
          <div className="card px-5 py-4">
            <p className="text-[10px] font-medium tracking-[0.06em] uppercase" style={{ color: "var(--text-6)" }}>
              Depenses
            </p>
            <p className="tnum text-lg font-semibold mt-1.5" style={{ color: "var(--red)" }}>
              {formatEUR(lastMonth.expenses)}
            </p>
          </div>
          <div className="card px-5 py-4">
            <p className="text-[10px] font-medium tracking-[0.06em] uppercase" style={{ color: "var(--text-6)" }}>
              Taux d&apos;epargne
            </p>
            <p className="tnum text-lg font-semibold mt-1.5" style={{ color: "var(--text-1)" }}>
              {savingsRate.toFixed(1)}%
            </p>
          </div>
        </div>
      )}

      {/* Top categories */}
      <div className="card p-6">
        <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-5" style={{ color: "var(--text-5)" }}>
          Top categories (3 mois)
        </h3>
        <div className="space-y-3">
          {categories.map((c, i) => {
            const maxTotal = categories[0]?.total ?? 1;
            const pct = (c.total / maxTotal) * 100;
            return (
              <div
                key={c.category}
                className="flex items-center gap-4 py-2 px-2 -mx-2 rounded-lg transition-colors cursor-default"
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <div
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[13px]" style={{ color: "var(--text-2)" }}>
                      {CATEGORY_LABELS[c.category] || c.category}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="tnum text-[13px] font-medium" style={{ color: "var(--text-1)" }}>
                        {formatEUR(c.total)}
                      </span>
                      <span className="tnum text-[11px] w-[32px] text-right" style={{ color: "var(--text-5)" }}>
                        {c.count}x
                      </span>
                    </div>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                        opacity: 0.5,
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
