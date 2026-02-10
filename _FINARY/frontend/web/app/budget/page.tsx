"use client";

import { useMemo, useState, useCallback } from "react";
import { useMonthlyBudget, useCategorySpending, useCategoryTransactions } from "@/lib/hooks/useApi";
import { formatEUR, CATEGORY_LABELS, CHART_COLORS } from "@/lib/utils";
import { BudgetChart } from "@/components/charts/BudgetChart";
import { PageHeader, Badge, Section, StatCard, DetailSheet } from "@/components/ds";
import {
  generateMonthlyBudget,
  generateCategorySpending,
} from "@/lib/fixtures";

export default function BudgetPage() {
  const { data: apiMonthly } = useMonthlyBudget(12);
  const { data: apiCategories } = useCategorySpending(3);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const { data: categoryTxs } = useCategoryTransactions(selectedCategory, 3);

  const monthly = useMemo(() => {
    if (apiMonthly && apiMonthly.length > 0) return apiMonthly;
    return generateMonthlyBudget(12);
  }, [apiMonthly]);

  const categories = useMemo(() => {
    if (apiCategories && apiCategories.length > 0) return apiCategories;
    return generateCategorySpending();
  }, [apiCategories]);

  const lastMonth = monthly[monthly.length - 1];
  const savingsRate = lastMonth && lastMonth.income > 0
    ? ((lastMonth.income - lastMonth.expenses) / lastMonth.income) * 100
    : lastMonth ? -100 : 0;

  // Month detail: income + expense breakdown
  const monthDetail = useMemo(() => {
    if (!selectedMonth || !apiMonthly) return null;
    return apiMonthly.find((m) => m.month === selectedMonth) ?? null;
  }, [selectedMonth, apiMonthly]);

  const openCategory = useCallback((cat: string) => {
    setSelectedCategory(cat);
    setSelectedMonth(null);
  }, []);

  const openMonth = useCallback((month: string) => {
    setSelectedMonth(month);
    setSelectedCategory(null);
  }, []);

  const closeSheet = useCallback(() => {
    setSelectedCategory(null);
    setSelectedMonth(null);
  }, []);

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
        <BudgetChart data={monthly} onBarClick={openMonth} />
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
                className="flex items-center gap-4 py-2 px-2 -mx-2 rounded-lg transition-colors cursor-pointer hover:bg-bg-hover"
                onClick={() => openCategory(c.category)}
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

      {/* Category detail sheet */}
      <DetailSheet
        open={!!selectedCategory}
        onClose={closeSheet}
        title={CATEGORY_LABELS[selectedCategory ?? ""] || selectedCategory || ""}
        subtitle={`${categoryTxs?.length ?? 0} transactions · 3 derniers mois`}
      >
        {categoryTxs && categoryTxs.length > 0 ? (
          <div className="space-y-1">
            {categoryTxs.map((tx, i) => (
              <div
                key={`${tx.date}-${i}`}
                className="flex items-center justify-between py-3 px-2 -mx-2 rounded-lg hover:bg-bg-hover transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-body text-t-2 truncate">{tx.merchant || tx.description.split("|")[0].trim()}</p>
                  <p className="text-label text-t-5 mt-0.5">
                    {new Date(tx.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}
                    {tx.bank === "trade_republic" ? " · TR" : tx.bank === "boursobank" ? " · Bourso" : ""}
                  </p>
                </div>
                <span className="tnum text-body font-medium text-loss ml-3 shrink-0">
                  {formatEUR(tx.amount)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-body text-t-5 text-center py-8">Aucune transaction</p>
        )}
      </DetailSheet>

      {/* Month detail sheet */}
      <DetailSheet
        open={!!selectedMonth}
        onClose={closeSheet}
        title={selectedMonth ? new Date(selectedMonth + "-01").toLocaleDateString("fr-FR", { month: "long", year: "numeric" }) : ""}
        subtitle="Résumé mensuel"
      >
        {monthDetail && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="card p-4">
                <p className="text-label text-t-5 uppercase">Revenus</p>
                <p className="tnum text-heading font-semibold text-gain mt-1">{formatEUR(monthDetail.income)}</p>
              </div>
              <div className="card p-4">
                <p className="text-label text-t-5 uppercase">Dépenses</p>
                <p className="tnum text-heading font-semibold text-loss mt-1">{formatEUR(monthDetail.expenses)}</p>
              </div>
            </div>
            <div className="card p-4">
              <p className="text-label text-t-5 uppercase">Épargne</p>
              <p className={`tnum text-heading font-semibold mt-1 ${monthDetail.income - monthDetail.expenses >= 0 ? "text-gain" : "text-loss"}`}>
                {formatEUR(monthDetail.income - monthDetail.expenses)}
              </p>
              <p className="tnum text-label text-t-5 mt-1">
                Taux d&apos;épargne : {monthDetail.savings_rate.toFixed(1)}%
              </p>
            </div>
            {/* Categories breakdown for that month */}
            {monthDetail.categories && (
              <div className="space-y-2">
                <p className="text-label text-t-5 uppercase mb-3">Par catégorie</p>
                {Object.entries(monthDetail.categories)
                  .sort(([, a], [, b]) => b - a)
                  .map(([cat, amt], i) => (
                    <div
                      key={cat}
                      className="flex items-center justify-between py-2 px-2 -mx-2 rounded-lg hover:bg-bg-hover cursor-pointer transition-colors"
                      onClick={() => { setSelectedMonth(null); openCategory(cat); }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                        <span className="text-body text-t-3">{CATEGORY_LABELS[cat] || cat}</span>
                      </div>
                      <span className="tnum text-body font-medium text-t-1">{formatEUR(amt)}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}
      </DetailSheet>
    </div>
  );
}
