"use client";

import { useCosts } from "@/lib/hooks/useApi";
import { formatEUR, CHART_COLORS } from "@/lib/utils";
import { Loading, ErrorState, PageHeader, Section, StatCard } from "@/components/ds";

interface CostItem { name: string; amount: number; type: string; category?: string }
interface AnnualFees { tr_trading: number; tr_pfof_spread_est: number; ibkr_commissions_est: number; etf_ter_annual: number; margin_interest_annual: number; [k: string]: number }
interface CostsData { monthly_total: number; breakdown: CostItem[]; annual_fees: AnnualFees }

export default function CostsPage() {
  const { data: rawCosts, isLoading, error } = useCosts();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!rawCosts) return null;

  const costs = rawCosts as unknown as CostsData;

  const annualTotal = Object.values(costs.annual_fees).reduce((s, v) => s + (typeof v === "number" ? v : 0), 0);

  return (
    <div className="space-y-8">
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
          {costs.breakdown.map((item: CostItem, i: number) => {
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
                      {item.category || item.type}
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
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-5">
          {costs.annual_fees.tr_trading > 0 && (
            <StatCard label="Trading TR (1€/trade)" value={costs.annual_fees.tr_trading} color={CHART_COLORS[0]} />
          )}
          {costs.annual_fees.tr_pfof_spread_est > 0 && (
            <StatCard label="Spread PFOF TR" value={costs.annual_fees.tr_pfof_spread_est} detail="~0.2% du capital TR" color={CHART_COLORS[1]} />
          )}
          {costs.annual_fees.ibkr_commissions_est > 0 && (
            <StatCard label="Commissions IBKR" value={costs.annual_fees.ibkr_commissions_est} detail="Tiered ~$2/trade" color={CHART_COLORS[3]} />
          )}
          {costs.annual_fees.etf_ter_annual > 0 && (
            <StatCard label="TER ETF" value={costs.annual_fees.etf_ter_annual} detail="Frais de gestion annuels" color={CHART_COLORS[4]} />
          )}
          {costs.annual_fees.margin_interest_annual > 0 && (
            <StatCard label="Intérêts Marge IBKR" value={costs.annual_fees.margin_interest_annual} detail="~5.83% sur solde débiteur" color="var(--orange)" />
          )}
        </div>
      </Section>

      {/* Impact */}
      <Section title="Impact sur la performance">
        <div className="grid grid-cols-2 gap-5">
          <StatCard
            label="Coût annuel total"
            value={annualTotal + costs.monthly_total * 12}
            tone="negative"
          />
          <div className="bg-bg-hover p-5 rounded-lg">
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
