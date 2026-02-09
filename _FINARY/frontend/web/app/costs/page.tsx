"use client";

import { useCosts } from "@/lib/hooks/useApi";
import { formatEUR, CHART_COLORS } from "@/lib/utils";
import { Loading, ErrorState, PageHeader, Section, StatCard } from "@/components/ds";

interface CostItem { name: string; amount: number; type: string; category?: string; rate_source?: string; remaining?: number; insurance?: number; detail?: string }
interface AnnualFee { amount: number; label: string; detail?: string; rate_source?: string }
interface CostsData {
  monthly_total: number;
  breakdown: CostItem[];
  annual_fees: Record<string, AnnualFee>;
  annual_total: number;
  net_worth: number;
  pct_of_patrimoine: number;
  tr_cash_interest_annual: number;
  missing_data: string[];
  ter_details: { isin: string; name: string; ter: number; annual_cost: number }[];
}

function SourceBadge({ source }: { source?: string }) {
  if (!source) return null;
  const labels: Record<string, [string, string]> = {
    scraped_ca: ["CA", "bg-green-900/30 text-green-400"],
    scraped_ibkr: ["IBKR", "bg-blue-900/30 text-blue-400"],
    known_ter: ["TER", "bg-purple-900/30 text-purple-400"],
  };
  const [label, cls] = labels[source] || [source, "bg-bg-hover text-t-4"];
  return <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${cls}`}>{label}</span>;
}

export default function CostsPage() {
  const { data: rawCosts, isLoading, error } = useCosts();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!rawCosts) return null;

  const costs = rawCosts as unknown as CostsData;
  const annualFeeList = Object.values(costs.annual_fees);
  const annualTotal = costs.annual_total;

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
                    <SourceBadge source={item.rate_source} />
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="tnum text-body font-semibold text-t-1">{formatEUR(item.amount)}</span>
                    <span className="tnum text-label w-[38px] text-right text-t-5">{pct.toFixed(0)}%</span>
                  </div>
                </div>
                {item.remaining && (
                  <p className="text-caption text-t-5 ml-[22px]">Restant: {formatEUR(item.remaining)}</p>
                )}
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.6 }} />
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* Annual fees — only real data */}
      {annualFeeList.length > 0 && (
        <Section
          title="Frais annuels vérifiés"
          footer={
            <>
              <span className="text-body font-medium text-t-3">Total annuel vérifié</span>
              <span className="tnum text-title font-semibold text-loss">{formatEUR(annualTotal)}</span>
            </>
          }
        >
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-5">
            {annualFeeList.map((fee, i) => (
              <div key={i} className="bg-bg-hover p-5 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <p className="text-caption font-medium uppercase text-t-5">{fee.label}</p>
                  <SourceBadge source={fee.rate_source} />
                </div>
                <p className="tnum text-heading font-semibold text-loss">{formatEUR(fee.amount)}</p>
                {fee.detail && <p className="text-caption text-t-4 mt-1">{fee.detail}</p>}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* TR cash interest (income) */}
      {costs.tr_cash_interest_annual > 0 && (
        <Section title="Revenus passifs">
          <div className="grid grid-cols-2 gap-5">
            <div className="bg-bg-hover p-5 rounded-lg">
              <p className="text-caption font-medium uppercase mb-2 text-t-5">Intérêts TR Cash (2% p.a.)</p>
              <p className="tnum text-heading font-semibold text-gain">+{formatEUR(costs.tr_cash_interest_annual)}</p>
            </div>
          </div>
        </Section>
      )}

      {/* Impact */}
      <Section title="Impact sur la performance">
        <div className="grid grid-cols-2 gap-5">
          <StatCard
            label="Coût annuel total"
            value={annualTotal + costs.monthly_total * 12}
            tone="negative"
          />
          <div className="bg-bg-hover p-5 rounded-lg">
            <p className="text-caption font-medium uppercase mb-2 text-t-5">% du patrimoine net</p>
            <p className="tnum text-heading font-semibold text-warn">
              {((annualTotal + costs.monthly_total * 12) / Math.max(1, costs.net_worth) * 100).toFixed(2)}%
            </p>
            <p className="text-caption text-t-5 mt-1">Patrimoine: {formatEUR(costs.net_worth)}</p>
          </div>
        </div>
      </Section>

      {/* Missing data notice */}
      {costs.missing_data && costs.missing_data.length > 0 && (
        <div className="bg-warn-bg/30 border border-warn/20 rounded-lg p-4">
          <p className="text-caption font-semibold text-warn mb-2">Données manquantes</p>
          <ul className="text-caption text-t-4 space-y-1">
            {costs.missing_data.map((msg, i) => (
              <li key={i}>• {msg}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
