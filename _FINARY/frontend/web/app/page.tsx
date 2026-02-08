"use client";

import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { BreakdownDonut } from "@/components/dashboard/BreakdownDonut";
import { InstitutionBar } from "@/components/dashboard/InstitutionBar";
import { useNetWorth } from "@/lib/hooks/useApi";

export default function HomePage() {
  const { data: networth, isLoading, error } = useNetWorth();

  if (isLoading) return <div className="text-gray-500">Chargement...</div>;
  if (error)
    return <div className="text-red-500">Erreur: {error.message}</div>;
  if (!networth) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Patrimoine</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <NetWorthCard
          label="Patrimoine net"
          value={networth.net_worth}
          variation={networth.variation_day}
        />
        <NetWorthCard label="Total actifs" value={networth.total_assets} />
        <NetWorthCard
          label="Total passifs"
          value={networth.total_liabilities}
          negative
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <BreakdownDonut breakdown={networth.breakdown} />
        <InstitutionBar institutions={networth.by_institution} />
      </div>
    </div>
  );
}
