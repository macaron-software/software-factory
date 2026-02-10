"use client";

import { useMemo, useState, useCallback } from "react";
import { useMonthlyBudget, useCategorySpending, useCategoryTransactions, useBudgetProjections } from "@/lib/hooks/useApi";
import { formatEUR, CATEGORY_LABELS, CHART_COLORS } from "@/lib/utils";
import { BudgetChart } from "@/components/charts/BudgetChart";
import { PageHeader, Badge, Section, StatCard, DetailSheet, SourceBadge } from "@/components/ds";
import { TrendingUp, TrendingDown, PiggyBank, ArrowRight, Target } from "lucide-react";

/* ────────────── Mini Donut (reuse from insights) ────────────── */
function MiniDonut({ slices, size = 80 }: { slices: { pct: number; color: string }[]; size?: number }) {
  const r = size / 2 - 4;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border-1)" strokeWidth={8} />
      {slices.map((s, i) => {
        const dash = (s.pct / 100) * c;
        const el = (
          <circle
            key={i}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={s.color}
            strokeWidth={8}
            strokeDasharray={`${dash} ${c - dash}`}
            strokeDashoffset={-offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        );
        offset += dash;
        return el;
      })}
    </svg>
  );
}

/* ────────────── Period selector ────────────── */
function PeriodSelector({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const opts = [3, 6, 12];
  return (
    <div className="flex gap-1 p-0.5 rounded-lg" style={{ background: "var(--bg-2)" }}>
      {opts.map((o) => (
        <button
          key={o}
          className={`px-3 py-1 text-xs rounded-md transition-all ${value === o ? "font-semibold" : ""}`}
          style={{
            background: value === o ? "var(--bg-3)" : "transparent",
            color: value === o ? "var(--text-1)" : "var(--text-5)",
          }}
          onClick={() => onChange(o)}
        >
          {o}M
        </button>
      ))}
    </div>
  );
}

export default function BudgetPage() {
  const [period, setPeriod] = useState(12);
  const { data: apiMonthly } = useMonthlyBudget(period);
  const { data: apiCategories } = useCategorySpending(period);
  const { data: projections } = useBudgetProjections();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const { data: categoryTxs } = useCategoryTransactions(selectedCategory, period);

  const monthly = useMemo(() => apiMonthly ?? [], [apiMonthly]);
  const categories = useMemo(() => apiCategories ?? [], [apiCategories]);

  // Current & previous month (skip partial current)
  const today = new Date();
  const currentMonthKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  const fullMonths = monthly.filter((m) => m.month !== currentMonthKey);
  const lastFull = fullMonths[fullMonths.length - 1];
  const prevFull = fullMonths[fullMonths.length - 2];

  // Averages (full months only)
  const avgIncome = fullMonths.length > 0 ? fullMonths.reduce((s, m) => s + m.income, 0) / fullMonths.length : 0;
  const avgExpenses = fullMonths.length > 0 ? fullMonths.reduce((s, m) => s + m.expenses, 0) / fullMonths.length : 0;
  const avgSavings = avgIncome - avgExpenses;
  const avgSavingsRate = avgIncome > 0 ? (avgSavings / avgIncome) * 100 : 0;

  // MoM evolution
  const momExpenses = lastFull && prevFull && prevFull.expenses > 0
    ? ((lastFull.expenses - prevFull.expenses) / prevFull.expenses) * 100
    : 0;

  // Donut data from categories
  const totalCatSpend = categories.reduce((s, c) => s + c.total, 0);
  const donutSlices = categories.slice(0, 8).map((c, i) => ({
    pct: totalCatSpend > 0 ? (c.total / totalCatSpend) * 100 : 0,
    color: CHART_COLORS[i % CHART_COLORS.length],
  }));
  const otherPct = 100 - donutSlices.reduce((s, d) => s + d.pct, 0);
  if (otherPct > 0.5) donutSlices.push({ pct: otherPct, color: "var(--text-6)" });

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

  const savingsRate = lastFull && lastFull.income > 0
    ? ((lastFull.income - lastFull.expenses) / lastFull.income) * 100
    : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        label="Budget"
        value={lastFull ? lastFull.income - lastFull.expenses : 0}
        right={
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <Badge variant={savingsRate >= 20 ? "gain" : savingsRate >= 0 ? "neutral" : "loss"}>
                {savingsRate.toFixed(0)}% épargné
              </Badge>
              <PeriodSelector value={period} onChange={setPeriod} />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-label text-t-5">
                {lastFull ? new Date(lastFull.month + "-01").toLocaleDateString("fr-FR", { month: "long", year: "numeric" }) : ""}
              </span>
              <SourceBadge source="scraped" />
            </div>
          </div>
        }
      />

      {/* ────── KPI Cards ────── */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp size={14} style={{ color: "var(--green)" }} />
            <span className="text-label text-t-5 uppercase">Revenus moy.</span>
          </div>
          <p className="tnum text-xl font-semibold text-gain">{formatEUR(avgIncome)}</p>
          {lastFull?.salary ? (
            <p className="tnum text-label text-t-5 mt-1">
              dont salaire {formatEUR(lastFull.salary)}
            </p>
          ) : null}
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown size={14} style={{ color: "var(--red)" }} />
            <span className="text-label text-t-5 uppercase">Dépenses moy.</span>
          </div>
          <p className="tnum text-xl font-semibold text-loss">{formatEUR(avgExpenses)}</p>
          {momExpenses !== 0 && (
            <p className="tnum text-label mt-1" style={{ color: momExpenses > 0 ? "var(--red)" : "var(--green)" }}>
              {momExpenses > 0 ? "+" : ""}{momExpenses.toFixed(0)}% M/M
            </p>
          )}
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <PiggyBank size={14} style={{ color: "var(--accent)" }} />
            <span className="text-label text-t-5 uppercase">Épargne moy.</span>
          </div>
          <p className={`tnum text-xl font-semibold ${avgSavings >= 0 ? "text-gain" : "text-loss"}`}>
            {formatEUR(avgSavings)}
          </p>
          <p className="tnum text-label text-t-5 mt-1">{avgSavingsRate.toFixed(0)}% du revenu</p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target size={14} style={{ color: "var(--text-3)" }} />
            <span className="text-label text-t-5 uppercase">Projection Y</span>
          </div>
          {projections?.yearly ? (
            <>
              <p className={`tnum text-xl font-semibold ${projections.yearly.projected_savings >= 0 ? "text-gain" : "text-loss"}`}>
                {formatEUR(projections.yearly.projected_savings)}
              </p>
              <p className="tnum text-label text-t-5 mt-1">
                {formatEUR(projections.yearly.projected_income)} rev. / an
              </p>
            </>
          ) : (
            <p className="text-label text-t-5">—</p>
          )}
        </div>
      </div>

      {/* ────── Revenue vs Expenses Chart ────── */}
      <Section title="Revenus vs Dépenses">
        <BudgetChart data={monthly} onBarClick={openMonth} />
      </Section>

      {/* ────── Projections M+1 to M+3 ────── */}
      {projections?.projections && projections.projections.length > 0 && (
        <Section title="Projections">
          <div className="grid grid-cols-3 gap-4">
            {projections.projections.map((p) => {
              const monthLabel = new Date(p.month + "-01").toLocaleDateString("fr-FR", { month: "short", year: "2-digit" });
              return (
                <div key={p.month} className="card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-label text-t-5 uppercase">{monthLabel}</span>
                    <ArrowRight size={12} style={{ color: "var(--text-6)" }} />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-label text-t-4">Revenus</span>
                      <span className="tnum text-body text-gain">{formatEUR(p.projected_income)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-label text-t-4">Dépenses</span>
                      <span className="tnum text-body text-loss">{formatEUR(p.projected_expenses)}</span>
                    </div>
                    <div className="flex justify-between pt-2" style={{ borderTop: "1px solid var(--border-1)" }}>
                      <span className="text-label text-t-3">Épargne</span>
                      <span className={`tnum text-body font-semibold ${p.projected_savings >= 0 ? "text-gain" : "text-loss"}`}>
                        {formatEUR(p.projected_savings)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-label text-t-6 mt-2 text-center">
            Basé sur {projections.basis_months} mois complets · Moyenne glissante
          </p>
        </Section>
      )}

      {/* ────── Categories Donut + List ────── */}
      <Section title={`Dépenses par catégorie · ${period} mois`}>
        <div className="flex gap-8">
          {/* Donut */}
          <div className="flex flex-col items-center gap-2 shrink-0">
            <div className="relative">
              <MiniDonut slices={donutSlices} size={140} />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="tnum text-lg font-semibold text-t-1">{formatEUR(totalCatSpend)}</span>
                <span className="text-label text-t-5">total</span>
              </div>
            </div>
          </div>

          {/* Category list */}
          <div className="flex-1 space-y-1 min-w-0">
            {categories.map((c, i) => {
              const pct = totalCatSpend > 0 ? (c.total / totalCatSpend) * 100 : 0;
              const avgPerMonth = period > 0 ? c.total / period : c.total;
              return (
                <div
                  key={c.category}
                  className="flex items-center gap-3 py-2 px-2 -mx-2 rounded-lg transition-colors cursor-pointer hover:bg-bg-hover"
                  onClick={() => openCategory(c.category)}
                >
                  <div
                    className="w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-body text-t-2">
                        {CATEGORY_LABELS[c.category] || c.category}
                      </span>
                      <div className="flex items-center gap-4">
                        <span className="tnum text-label text-t-5 w-[50px] text-right">{pct.toFixed(0)}%</span>
                        <span className="tnum text-body font-medium text-t-1 w-[90px] text-right">{formatEUR(c.total)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <div className="bar-track flex-1">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                            opacity: 0.5,
                          }}
                        />
                      </div>
                      <span className="tnum text-[10px] text-t-6 w-[70px] text-right shrink-0">
                        ~{formatEUR(avgPerMonth)}/mo
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      {/* ────── Category Detail Sheet ────── */}
      <DetailSheet
        open={!!selectedCategory}
        onClose={closeSheet}
        title={CATEGORY_LABELS[selectedCategory ?? ""] || selectedCategory || ""}
        subtitle={`${categoryTxs?.length ?? 0} transactions · ${period} derniers mois`}
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

      {/* ────── Month Detail Sheet ────── */}
      <DetailSheet
        open={!!selectedMonth}
        onClose={closeSheet}
        title={selectedMonth ? new Date(selectedMonth + "-01").toLocaleDateString("fr-FR", { month: "long", year: "numeric" }) : ""}
        subtitle="Résumé mensuel"
      >
        {(() => {
          const md = selectedMonth ? monthly.find((m) => m.month === selectedMonth) : null;
          if (!md) return null;
          const net = md.income - md.expenses;
          return (
            <div className="space-y-6">
              <div className="grid grid-cols-3 gap-3">
                <div className="card p-4">
                  <p className="text-label text-t-5 uppercase">Revenus</p>
                  <p className="tnum text-heading font-semibold text-gain mt-1">{formatEUR(md.income)}</p>
                  {md.salary ? <p className="tnum text-label text-t-5 mt-1">Salaire {formatEUR(md.salary)}</p> : null}
                </div>
                <div className="card p-4">
                  <p className="text-label text-t-5 uppercase">Dépenses</p>
                  <p className="tnum text-heading font-semibold text-loss mt-1">{formatEUR(md.expenses)}</p>
                  <p className="tnum text-label text-t-5 mt-1">{md.tx_count ?? "?"} transactions</p>
                </div>
                <div className="card p-4">
                  <p className="text-label text-t-5 uppercase">Épargne</p>
                  <p className={`tnum text-heading font-semibold mt-1 ${net >= 0 ? "text-gain" : "text-loss"}`}>
                    {formatEUR(net)}
                  </p>
                  <p className="tnum text-label text-t-5 mt-1">
                    {md.savings_rate?.toFixed(0) ?? "0"}%
                  </p>
                </div>
              </div>
              {md.categories && (
                <div className="space-y-2">
                  <p className="text-label text-t-5 uppercase mb-3">Par catégorie</p>
                  {Object.entries(md.categories)
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
          );
        })()}
      </DetailSheet>
    </div>
  );
}
