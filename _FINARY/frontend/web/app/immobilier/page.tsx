"use client";

import { useSCA } from "@/lib/hooks/useApi";
import { formatEUR, formatNumber, CHART_COLORS } from "@/lib/utils";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { Loading, ErrorState, PageHeader, Badge, Section, StatCard } from "@/components/ds";

export default function ImmobilierPage() {
  const { data: sca, isLoading, error } = useSCA();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!sca) return null;

  const prop = sca.property;
  const fin = sca.financials;
  const gainPct = prop.bourso_estimate > 0 && fin.total_verse > 0
    ? ((sca.your_share_property_value - fin.total_verse) / fin.total_verse * 100) : 0;
  const gainEur = sca.your_share_property_value - fin.total_verse;

  const ownershipData = [
    { name: "Votre part", value: sca.ownership_pct },
    { name: sca.co_associate.name, value: sca.co_associate.ownership_pct },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        label={`Immobilier — ${sca.name}`}
        value={sca.your_share_property_value}
        right={
          <div className="flex items-center gap-2">
            <span className={`tnum text-body font-medium ${gainEur >= 0 ? "text-gain" : "text-loss"}`}>
              {gainEur >= 0 ? "+" : ""}{formatEUR(gainEur)}
            </span>
            <Badge variant={gainEur >= 0 ? "gain" : "loss"}>
              {gainPct >= 0 ? "+" : ""}{gainPct.toFixed(1)}%
            </Badge>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Property card */}
        <Section title="Propriété">
          <div className="space-y-3">
            <InfoRow label="Adresse" value={prop.address} />
            <InfoRow label="Type" value={`${prop.type} — ${prop.rooms} pièces`} />
            <InfoRow label="Surface" value={`${prop.surface_m2} m²`} />
            <InfoRow label="DPE" value={prop.dpe_score} />
            <InfoRow label="Date d'achat" value={prop.purchase_date} />
            <InfoRow label="Prix/m² estimé" value={formatEUR(prop.price_per_m2_estimate)} />
            <div className="pt-3 mt-3 border-t border-bd-1">
              <InfoRow label="Estimation Bourso" value={formatEUR(prop.bourso_estimate)} highlight />
              <p className="text-label mt-1 text-right text-t-5">
                {formatEUR(prop.bourso_estimate_range.low)} — {formatEUR(prop.bourso_estimate_range.high)}
              </p>
            </div>
          </div>
        </Section>

        {/* Ownership chart */}
        <Section title="Répartition SCA">
          <div className="flex items-center gap-6">
            <div className="w-[140px] h-[140px] shrink-0 relative">
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-[1]">
                <span className="tnum text-title font-semibold text-t-1">
                  {sca.ownership_pct.toFixed(1)}%
                </span>
                <span className="text-caption text-t-5">Votre part</span>
              </div>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={ownershipData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={65}
                    dataKey="value"
                    stroke="var(--bg-3)"
                    strokeWidth={2}
                    startAngle={90}
                    endAngle={-270}
                  >
                    <Cell fill={CHART_COLORS[3]} />
                    <Cell fill={CHART_COLORS[0]} opacity={0.5} />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-3 flex-1">
              <div>
                <p className="text-label font-medium text-t-2">Vous</p>
                <p className="tnum text-label text-t-5">
                  {formatNumber(sca.parts, 0)} parts · {sca.ownership_pct.toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-label font-medium text-t-4">{sca.co_associate.name}</p>
                <p className="tnum text-label text-t-5">
                  {formatNumber(sca.co_associate.parts, 0)} parts · {sca.co_associate.ownership_pct.toFixed(1)}%
                </p>
              </div>
            </div>
          </div>
        </Section>
      </div>

      {/* Financial details */}
      <Section title="Situation financière SCA">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Capital versé" value={fin.capital_verse} />
          <StatCard label="Avances CCA" value={fin.cca_avances} />
          <StatCard label="Total versé" value={fin.total_verse} tone="accent" />
          <StatCard label="Charges Q.P." value={fin.total_charges_qp} />
          <StatCard label="AF Impayés" value={fin.af_impayes} tone="negative" />
          <StatCard label="Solde net" value={fin.solde_net} tone="positive" />
          <StatCard label="Compte bancaire" value={fin.bank_account_balance} />
          <StatCard label="Valeur terrain" value={sca.property.terrain_value_book} />
        </div>
      </Section>
    </div>
  );
}

function InfoRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-label text-t-5">{label}</span>
      <span className={`tnum text-body font-medium ${highlight ? "text-accent" : "text-t-1"}`}>
        {value}
      </span>
    </div>
  );
}
