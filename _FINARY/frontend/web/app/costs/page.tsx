"use client";

import { useCosts } from "@/lib/hooks/useApi";
import { formatEUR, CHART_COLORS } from "@/lib/utils";

export default function CostsPage() {
  const { data: costs, isLoading, error } = useCosts();

  if (isLoading)
    return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;
  if (error)
    return <div className="text-[13px]" style={{ color: "var(--red)" }}>Erreur de connexion API</div>;
  if (!costs) return null;

  const annualTotal =
    costs.annual_fees.tr_trading +
    costs.annual_fees.ibkr_commissions_est +
    costs.annual_fees.margin_interest_annual;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-2" style={{ color: "var(--text-5)" }}>
          Coûts & Frais
        </p>
        <p className="tnum text-[32px] font-extralight tracking-tight leading-none" style={{ color: "var(--text-1)" }}>
          {formatEUR(costs.monthly_total)}<span className="text-[15px] font-normal" style={{ color: "var(--text-5)" }}>/mois</span>
        </p>
      </div>

      {/* Monthly costs breakdown */}
      <div className="card p-6">
        <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-4" style={{ color: "var(--text-5)" }}>
          Mensualités récurrentes
        </h3>
        <div className="space-y-3">
          {costs.breakdown.map((item, i) => {
            const pct = costs.monthly_total > 0 ? (item.amount / costs.monthly_total * 100) : 0;
            const color = item.type === "margin" ? "var(--orange)" : CHART_COLORS[i % CHART_COLORS.length];
            return (
              <div key={i}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-3">
                    <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-[13px]" style={{ color: "var(--text-2)" }}>{item.name}</span>
                    <span
                      className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                      style={{
                        background: item.type === "margin" ? "var(--orange-bg)" : "var(--accent-bg)",
                        color: item.type === "margin" ? "var(--orange)" : "var(--accent)",
                      }}
                    >
                      {item.type}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="tnum text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>
                      {formatEUR(item.amount)}
                    </span>
                    <span className="tnum text-[11px] w-[38px] text-right" style={{ color: "var(--text-5)" }}>
                      {pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.6 }} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex items-center justify-between pt-4 mt-4" style={{ borderTop: "1px solid var(--border-1)" }}>
          <span className="text-[13px] font-medium" style={{ color: "var(--text-3)" }}>Total mensuel</span>
          <span className="tnum text-[15px] font-semibold" style={{ color: "var(--text-1)" }}>
            {formatEUR(costs.monthly_total)}
          </span>
        </div>
      </div>

      {/* Annual fees */}
      <div className="card p-6">
        <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-4" style={{ color: "var(--text-5)" }}>
          Frais annuels estimés
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <FeeCard
            label="Trading Trade Republic"
            value={costs.annual_fees.tr_trading}
            detail={`${costs.annual_fees.tr_trading.toFixed(0)} trades × 1€`}
            color={CHART_COLORS[0]}
          />
          <FeeCard
            label="Commissions IBKR"
            value={costs.annual_fees.ibkr_commissions_est}
            detail="Estimé (tiered $1/trade)"
            color={CHART_COLORS[3]}
          />
          <FeeCard
            label="Intérêts Marge IBKR"
            value={costs.annual_fees.margin_interest_annual}
            detail="~5.83% sur solde débiteur"
            color="var(--orange)"
          />
        </div>
        <div className="flex items-center justify-between pt-4 mt-4" style={{ borderTop: "1px solid var(--border-1)" }}>
          <span className="text-[13px] font-medium" style={{ color: "var(--text-3)" }}>Total annuel estimé</span>
          <span className="tnum text-[15px] font-semibold" style={{ color: "var(--red)" }}>
            {formatEUR(annualTotal)}
          </span>
        </div>
      </div>

      {/* Impact on performance */}
      <div className="card p-6">
        <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-4" style={{ color: "var(--text-5)" }}>
          Impact sur la performance
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 rounded-lg" style={{ background: "var(--bg-hover)" }}>
            <p className="text-[10px] font-medium tracking-[0.04em] uppercase mb-1" style={{ color: "var(--text-5)" }}>
              Coût annuel total
            </p>
            <p className="tnum text-[18px] font-semibold" style={{ color: "var(--red)" }}>
              {formatEUR(annualTotal + costs.monthly_total * 12)}
            </p>
          </div>
          <div className="p-3 rounded-lg" style={{ background: "var(--bg-hover)" }}>
            <p className="text-[10px] font-medium tracking-[0.04em] uppercase mb-1" style={{ color: "var(--text-5)" }}>
              % du patrimoine
            </p>
            <p className="tnum text-[18px] font-semibold" style={{ color: "var(--orange)" }}>
              {((annualTotal + costs.monthly_total * 12) / 87145 * 100).toFixed(2)}%
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function FeeCard({ label, value, detail, color }: {
  label: string;
  value: number;
  detail: string;
  color: string;
}) {
  return (
    <div className="p-4 rounded-lg" style={{ background: "var(--bg-hover)" }}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: color }} />
        <p className="text-[11px] font-medium" style={{ color: "var(--text-4)" }}>{label}</p>
      </div>
      <p className="tnum text-[18px] font-semibold" style={{ color: "var(--text-1)" }}>{formatEUR(value)}</p>
      <p className="text-[11px] mt-1" style={{ color: "var(--text-5)" }}>{detail}</p>
    </div>
  );
}
