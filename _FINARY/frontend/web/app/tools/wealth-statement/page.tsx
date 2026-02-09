"use client";

import { useNetWorth, usePortfolio, useAccounts } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";
import { Loading } from "@/components/ds";

interface StatementRow {
  label: string;
  value: number;
}

export default function WealthStatementPage() {
  const { data: networth, isLoading: nwLoading } = useNetWorth();
  const { data: positions } = usePortfolio();
  const { data: accounts } = useAccounts();

  if (nwLoading) return <Loading />;
  if (!networth) return null;

  const investmentTotal = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const checkingTotal = accounts?.filter((a) => a.account_type === "checking").reduce((s, a) => s + a.balance, 0) ?? 0;
  const savingsTotal = accounts?.filter((a) => a.account_type === "savings").reduce((s, a) => s + a.balance, 0) ?? 0;
  const peaTotal = accounts?.filter((a) => a.account_type === "pea").reduce((s, a) => s + a.balance, 0) ?? 0;
  const ctoTotal = accounts?.filter((a) => a.account_type === "cto").reduce((s, a) => s + a.balance, 0) ?? 0;

  const assets: StatementRow[] = [
    { label: "Comptes courants", value: checkingTotal },
    { label: "Livrets", value: savingsTotal },
    { label: "PEA", value: peaTotal },
    { label: "CTO", value: ctoTotal },
    { label: "Investissements (valeur marché)", value: investmentTotal },
    { label: "Immobilier", value: networth.breakdown.real_estate ?? 0 },
  ];

  const liabilities: StatementRow[] = [
    { label: "Emprunts immobiliers", value: networth.total_liabilities },
  ];

  const totalAssets = assets.reduce((s, r) => s + r.value, 0);
  const totalLiabilities = liabilities.reduce((s, r) => s + r.value, 0);

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <p className="text-label font-medium uppercase mb-2 text-t-5">
          Déclaration de patrimoine
        </p>
        <p className="text-[22px] font-light text-t-1">
          État au {new Date().toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
        </p>
      </div>

      {/* Assets */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3 border-b border-bd-1">
          <p className="text-body font-semibold text-t-1">Actifs</p>
        </div>
        {assets.map((row, i) => (
          <div
            key={row.label}
            className={`flex items-center justify-between px-5 py-3 ${i < assets.length - 1 ? "border-b border-bd-1" : ""}`}
          >
            <span className="text-body text-t-3">{row.label}</span>
            <span className="tnum text-body font-medium text-t-1">{formatEUR(row.value)}</span>
          </div>
        ))}
        <div className="flex items-center justify-between px-5 py-3 bg-bg-hover border-t border-bd-1">
          <span className="text-body font-semibold text-t-1">Total actifs</span>
          <span className="tnum text-title font-semibold text-t-1">{formatEUR(totalAssets)}</span>
        </div>
      </div>

      {/* Liabilities */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3 border-b border-bd-1">
          <p className="text-body font-semibold text-t-1">Passifs</p>
        </div>
        {liabilities.map((row, i) => (
          <div
            key={row.label}
            className={`flex items-center justify-between px-5 py-3 ${i < liabilities.length - 1 ? "border-b border-bd-1" : ""}`}
          >
            <span className="text-body text-t-3">{row.label}</span>
            <span className="tnum text-body font-medium text-loss">{formatEUR(row.value)}</span>
          </div>
        ))}
        <div className="flex items-center justify-between px-5 py-3 bg-bg-hover border-t border-bd-1">
          <span className="text-body font-semibold text-t-1">Total passifs</span>
          <span className="tnum text-title font-semibold text-loss">{formatEUR(totalLiabilities)}</span>
        </div>
      </div>

      {/* Net worth */}
      <div className="card p-7">
        <div className="flex items-center justify-between">
          <span className="text-title font-semibold text-t-1">Patrimoine net</span>
          <span className="tnum text-[22px] font-extralight text-accent">
            {formatEUR(totalAssets - totalLiabilities)}
          </span>
        </div>
      </div>
    </div>
  );
}
