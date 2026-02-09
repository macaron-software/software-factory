"use client";

import { useMemo } from "react";
import { useMonthlyBudget, useCategorySpending } from "@/lib/hooks/useApi";
import { formatEUR, CATEGORY_LABELS, CHART_COLORS } from "@/lib/utils";
import { BudgetChart } from "@/components/charts/BudgetChart";
import { PageHeader, Badge, Section, StatCard } from "@/components/ds";
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

  const lastMonth = monthly[monthly.length - 1];
  const savingsRate = lastMonth
    ? ((lastMonth.income - lastMonth.expenses) / lastMonth.income) * 100
    : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        label="Budget"
        value={lastMonth ? lastMonth.income - lastMonth.expenses : 0}
        right={
          lastMonth ? (
            <div className="flex flex-col items-end gap-1">
              <Badge variant={savingsRate >= 0 ? "gain" : "loss"}>
                {savingsRate.toFixed(0)}% du revenu
              </Badge>
              <span className="text-label text-t-5">épargne ce mois</span>
            </div>
          ) : undefined
        }
      />

      <Section title="Revenus vs Dépenses">
        <BudgetChart data={monthly} />
      </Section>

      {lastMonth && (
        <div className="grid grid-cols-3 gap-5">
          <StatCard label="Revenus" value={lastMonth.income} tone="positive" />
          <StatCard label="Dépenses" value={lastMonth.expenses} tone="negative" />
          <StatCard label="Taux d'épargne" value={0} tone="default" detail={`${savingsRate.toFixed(1)}%`} />
        </div>
      )}

      <Section title="Top catégories (3 mois)">
        <div className="space-y-3">
          {categories.map((c, i) => {
            const maxTotal = categories[0]?.total ?? 1;
            const pct = (c.total / maxTotal) * 100;
            return (
              <div
                key={c.category}
                className="flex items-center gap-4 py-2 px-2 -mx-2 rounded-lg transition-colors cursor-default hover:bg-bg-hover"
              >
                <div
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-body text-t-2">
                      {CATEGORY_LABELS[c.category] || c.category}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="tnum text-body font-medium text-t-1">{formatEUR(c.total)}</span>
                      <span className="tnum text-label w-[32px] text-right text-t-5">{c.count}x</span>
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
      </Section>
    </div>
  );
}
