"use client";

import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { BreakdownDonut } from "@/components/dashboard/BreakdownDonut";
import { InstitutionBar } from "@/components/dashboard/InstitutionBar";
import { NetWorthChart } from "@/components/charts/NetWorthChart";
import { useNetWorth } from "@/lib/hooks/useApi";
import { Loading, ErrorState } from "@/components/ds";

export default function HomePage() {
  const { data: networth, isLoading, error } = useNetWorth();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!networth) return null;

  return (
    <div className="space-y-6">
      <NetWorthChart />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <NetWorthCard
          label="Actifs"
          value={networth.total_assets}
          variation={networth.variation_month}
        />
        <NetWorthCard label="Passifs" value={networth.total_liabilities} negative />
        <NetWorthCard label="Investissements" value={networth.breakdown.investments} />
        <NetWorthCard
          label="Liquidités"
          value={networth.breakdown.cash + networth.breakdown.savings}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BreakdownDonut breakdown={networth.breakdown} />
        <InstitutionBar institutions={networth.by_institution} />
      </div>
    </div>
  );
}
