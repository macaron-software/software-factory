"use client";

import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { BreakdownDonut } from "@/components/dashboard/BreakdownDonut";
import { InstitutionBar } from "@/components/dashboard/InstitutionBar";
import { NetWorthChart } from "@/components/charts/NetWorthChart";
import { useNetWorth } from "@/lib/hooks/useApi";
import { formatEUR, formatPct } from "@/lib/utils";

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
    <div className="space-y-6">
      {/* Net worth evolution chart */}
      <NetWorthChart />

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <NetWorthCard
          label="Actifs"
          value={networth.total_assets}
          variation={networth.variation_month}
        />
        <NetWorthCard label="Passifs" value={networth.total_liabilities} negative />
        <NetWorthCard label="Investissements" value={networth.breakdown.investments} />
        <NetWorthCard
          label="Liquidites"
          value={networth.breakdown.cash + networth.breakdown.savings}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BreakdownDonut breakdown={networth.breakdown} />
        <InstitutionBar institutions={networth.by_institution} />
      </div>
    </div>
  );
}
