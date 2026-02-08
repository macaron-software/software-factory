"use client";

import { useNetWorth, usePortfolio, useAccounts } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";

interface StatementRow {
  label: string;
  value: number;
  indent?: boolean;
}

export default function WealthStatementPage() {
  const { data: networth, isLoading: nwLoading } = useNetWorth();
  const { data: positions } = usePortfolio();
  const { data: accounts } = useAccounts();

  if (nwLoading) return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;
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
    { label: "Investissements (valeur marche)", value: investmentTotal },
    { label: "Immobilier", value: networth.breakdown.real_estate ?? 0 },
  ];

  const liabilities: StatementRow[] = [
    { label: "Emprunts immobiliers", value: networth.total_liabilities },
  ];

  const totalAssets = assets.reduce((s, r) => s + r.value, 0);
  const totalLiabilities = liabilities.reduce((s, r) => s + r.value, 0);

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-2" style={{ color: "var(--text-5)" }}>
          Declaration de patrimoine
        </p>
        <p className="text-[22px] font-light" style={{ color: "var(--text-1)" }}>
          Etat au {new Date().toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
        </p>
      </div>

      {/* Assets */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3" style={{ borderBottom: "1px solid var(--border-1)" }}>
          <p className="text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>Actifs</p>
        </div>
        {assets.map((row, i) => (
          <div
            key={row.label}
            className="flex items-center justify-between px-5 py-3"
            style={{ borderBottom: i < assets.length - 1 ? "1px solid var(--border-1)" : "none" }}
          >
            <span className="text-[13px]" style={{ color: "var(--text-3)" }}>{row.label}</span>
            <span className="tnum text-[13px] font-medium" style={{ color: "var(--text-1)" }}>{formatEUR(row.value)}</span>
          </div>
        ))}
        <div className="flex items-center justify-between px-5 py-3" style={{ background: "var(--bg-hover)", borderTop: "1px solid var(--border-1)" }}>
          <span className="text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>Total actifs</span>
          <span className="tnum text-[15px] font-semibold" style={{ color: "var(--text-1)" }}>{formatEUR(totalAssets)}</span>
        </div>
      </div>

      {/* Liabilities */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3" style={{ borderBottom: "1px solid var(--border-1)" }}>
          <p className="text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>Passifs</p>
        </div>
        {liabilities.map((row, i) => (
          <div
            key={row.label}
            className="flex items-center justify-between px-5 py-3"
            style={{ borderBottom: i < liabilities.length - 1 ? "1px solid var(--border-1)" : "none" }}
          >
            <span className="text-[13px]" style={{ color: "var(--text-3)" }}>{row.label}</span>
            <span className="tnum text-[13px] font-medium" style={{ color: "var(--red)" }}>{formatEUR(row.value)}</span>
          </div>
        ))}
        <div className="flex items-center justify-between px-5 py-3" style={{ background: "var(--bg-hover)", borderTop: "1px solid var(--border-1)" }}>
          <span className="text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>Total passifs</span>
          <span className="tnum text-[15px] font-semibold" style={{ color: "var(--red)" }}>{formatEUR(totalLiabilities)}</span>
        </div>
      </div>

      {/* Net worth */}
      <div className="card p-5">
        <div className="flex items-center justify-between">
          <span className="text-[15px] font-semibold" style={{ color: "var(--text-1)" }}>Patrimoine net</span>
          <span className="tnum text-[22px] font-extralight" style={{ color: "var(--accent)" }}>
            {formatEUR(totalAssets - totalLiabilities)}
          </span>
        </div>
      </div>
    </div>
  );
}
