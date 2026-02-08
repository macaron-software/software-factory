"use client";

import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { BreakdownDonut } from "@/components/dashboard/BreakdownDonut";
import { InstitutionBar } from "@/components/dashboard/InstitutionBar";
import { useNetWorth } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";

export default function HomePage() {
  const { data: networth, isLoading, error } = useNetWorth();

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  if (error)
    return (
      <div className="text-[13px]" style={{ color: "var(--red)" }}>
        Erreur de connexion API
      </div>
    );
  if (!networth) return null;

  return (
    <div className="space-y-8">
      {/* Hero: Net worth */}
      <div>
        <p className="text-[13px] font-medium mb-1" style={{ color: "var(--text-5)" }}>
          Patrimoine net
        </p>
        <p className="tnum text-[40px] font-extralight tracking-tight leading-tight" style={{ color: "var(--text-1)" }}>
          {formatEUR(networth.net_worth)}
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <NetWorthCard label="Actifs" value={networth.total_assets} />
        <NetWorthCard label="Passifs" value={networth.total_liabilities} negative />
        <NetWorthCard label="Investissements" value={networth.breakdown.investments} />
        <NetWorthCard label="Liquidites" value={networth.breakdown.cash + networth.breakdown.savings} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BreakdownDonut breakdown={networth.breakdown} />
        <InstitutionBar institutions={networth.by_institution} />
      </div>
    </div>
  );
}
