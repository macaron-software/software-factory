"use client";

import { useCosts } from "@/lib/hooks/useApi";
import { formatEUR, CHART_COLORS } from "@/lib/utils";
import { Loading, ErrorState, PageHeader, Section, StatCard } from "@/components/ds";

export default function CostsPage() {
  const { data: costs, isLoading, error } = useCosts();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!costs) return null;

  const annualTotal =
    costs.annual_fees.tr_trading +
    costs.annual_fees.ibkr_commissions_est +
    costs.annual_fees.margin_interest_annual;

  return (
    <div className="space-y-6">
      <PageHeader label="Coûts & Frais" value={costs.monthly_total} suffix="/mois" />

      {/* Monthly costs */}
      <Section
        title="Mensualités récurrentes"
        footer={
          <>
            <span className="text-body font-medium text-t-3">Total mensuel</span>
            <span className="tnum text-title font-semibold text-t-1">{formatEUR(costs.monthly_total)}</span>
          </>
        }
      >
        <div className="space-y-3">
          {costs.breakdown.map((item, i) => {
            const pct = costs.monthly_total > 0 ? (item.amount / costs.monthly_total * 100) : 0;
            const color = item.type === "margin" ? "var(--orange)" : CHART_COLORS[i % CHART_COLORS.length];
            return (
              <div key={i}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-3">
                    <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-body text-t-2">{item.name}</span>
                    <span className={`text-caption font-medium px-1.5 py-0.5 rounded ${
                      item.type === "margin" ? "bg-warn-bg text-warn" : "bg-accent-bg text-accent"
                    }`}>
                      {item.type}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="tnum text-body font-semibold text-t-1">{formatEUR(item.amount)}</span>
                    <span className="tnum text-label w-[38px] text-right text-t-5">{pct.toFixed(0)}%</span>
                  </div>
                </div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.6 }} />
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* Annual fees */}
      <Section
        title="Frais annuels estimés"
        footer={
          <>
            <span className="text-body font-medium text-t-3">Total annuel estimé</span>
            <span className="tnum text-title font-semibold text-loss">{formatEUR(annualTotal)}</span>
          </>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <StatCard
            label="Trading Trade Republic"
            value={costs.annual_fees.tr_trading}
            detail={`${costs.annual_fees.tr_trading.toFixed(0)} trades × 1€`}
            color={CHART_COLORS[0]}
          />
          <StatCard
            label="Commissions IBKR"
            value={costs.annual_fees.ibkr_commissions_est}
            detail="Estimé (tiered $1/trade)"
            color={CHART_COLORS[3]}
          />
          <StatCard
            label="Intérêts Marge IBKR"
            value={costs.annual_fees.margin_interest_annual}
            detail="~5.83% sur solde débiteur"
            color="var(--orange)"
          />
        </div>
      </Section>

      {/* Impact */}
      <Section title="Impact sur la performance">
        <div className="grid grid-cols-2 gap-4">
          <StatCard
            label="Coût annuel total"
            value={annualTotal + costs.monthly_total * 12}
            tone="negative"
          />
          <div className="bg-bg-hover p-4 rounded-lg">
            <p className="text-caption font-medium uppercase mb-2 text-t-5">% du patrimoine</p>
            <p className="tnum text-heading font-semibold text-warn">
              {((annualTotal + costs.monthly_total * 12) / 87145 * 100).toFixed(2)}%
            </p>
          </div>
        </div>
      </Section>
    </div>
  );
}
