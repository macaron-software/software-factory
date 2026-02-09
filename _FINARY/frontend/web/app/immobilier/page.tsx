"use client";

import { useSCA } from "@/lib/hooks/useApi";
import { formatEUR, formatNumber, CHART_COLORS } from "@/lib/utils";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

export default function ImmobilierPage() {
  const { data: sca, isLoading, error } = useSCA();

  if (isLoading)
    return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;
  if (error)
    return <div className="text-[13px]" style={{ color: "var(--red)" }}>Erreur de connexion API</div>;
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
      {/* Header */}
      <div>
        <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-2" style={{ color: "var(--text-5)" }}>
          Immobilier — {sca.name}
        </p>
        <p className="tnum text-[32px] font-extralight tracking-tight leading-none" style={{ color: "var(--text-1)" }}>
          {formatEUR(sca.your_share_property_value)}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <span className="tnum text-[13px] font-medium" style={{ color: gainEur >= 0 ? "var(--green)" : "var(--red)" }}>
            {gainEur >= 0 ? "+" : ""}{formatEUR(gainEur)}
          </span>
          <span
            className="tnum text-[11px] font-medium px-2 py-0.5 rounded"
            style={{
              background: gainEur >= 0 ? "var(--green-bg)" : "var(--red-bg)",
              color: gainEur >= 0 ? "var(--green)" : "var(--red)",
            }}
          >
            {gainPct >= 0 ? "+" : ""}{gainPct.toFixed(1)}%
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Property card */}
        <div className="card p-6">
          <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-4" style={{ color: "var(--text-5)" }}>
            Propriété
          </h3>
          <div className="space-y-3">
            <InfoRow label="Adresse" value={prop.address} />
            <InfoRow label="Type" value={`${prop.type} — ${prop.rooms} pièces`} />
            <InfoRow label="Surface" value={`${prop.surface_m2} m²`} />
            <InfoRow label="DPE" value={prop.dpe_score} />
            <InfoRow label="Date d'achat" value={prop.purchase_date} />
            <InfoRow label="Prix/m² estimé" value={formatEUR(prop.price_per_m2_estimate)} />
            <div className="pt-3 mt-3" style={{ borderTop: "1px solid var(--border-1)" }}>
              <InfoRow label="Estimation Bourso" value={formatEUR(prop.bourso_estimate)} highlight />
              <div className="flex items-center gap-2 mt-1 ml-auto">
                <span className="text-[11px]" style={{ color: "var(--text-5)" }}>
                  {formatEUR(prop.bourso_estimate_range.low)} — {formatEUR(prop.bourso_estimate_range.high)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Ownership chart */}
        <div className="card p-6">
          <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-4" style={{ color: "var(--text-5)" }}>
            Répartition SCA
          </h3>
          <div className="flex items-center gap-6">
            <div className="w-[140px] h-[140px] shrink-0 relative">
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none" style={{ zIndex: 1 }}>
                <span className="tnum text-[15px] font-semibold" style={{ color: "var(--text-1)" }}>
                  {sca.ownership_pct.toFixed(1)}%
                </span>
                <span className="text-[10px]" style={{ color: "var(--text-5)" }}>Votre part</span>
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
                <p className="text-[12px] font-medium" style={{ color: "var(--text-2)" }}>Vous</p>
                <p className="tnum text-[11px]" style={{ color: "var(--text-5)" }}>
                  {formatNumber(sca.parts, 0)} parts · {sca.ownership_pct.toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-[12px] font-medium" style={{ color: "var(--text-4)" }}>{sca.co_associate.name}</p>
                <p className="tnum text-[11px]" style={{ color: "var(--text-5)" }}>
                  {formatNumber(sca.co_associate.parts, 0)} parts · {sca.co_associate.ownership_pct.toFixed(1)}%
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Financial details */}
      <div className="card p-6">
        <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-4" style={{ color: "var(--text-5)" }}>
          Situation financière SCA
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MiniCard label="Capital versé" value={formatEUR(fin.capital_verse)} />
          <MiniCard label="Avances CCA" value={formatEUR(fin.cca_avances)} />
          <MiniCard label="Total versé" value={formatEUR(fin.total_verse)} highlight />
          <MiniCard label="Charges Q.P." value={formatEUR(fin.total_charges_qp)} />
          <MiniCard label="AF Impayés" value={formatEUR(fin.af_impayes)} negative />
          <MiniCard label="Solde net" value={formatEUR(fin.solde_net)} positive />
          <MiniCard label="Compte bancaire" value={formatEUR(fin.bank_account_balance)} />
          <MiniCard label="Valeur terrain" value={formatEUR(sca.property.terrain_value_book)} />
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[12px]" style={{ color: "var(--text-5)" }}>{label}</span>
      <span
        className="tnum text-[13px] font-medium"
        style={{ color: highlight ? "var(--accent)" : "var(--text-1)" }}
      >
        {value}
      </span>
    </div>
  );
}

function MiniCard({ label, value, highlight, negative, positive }: {
  label: string;
  value: string;
  highlight?: boolean;
  negative?: boolean;
  positive?: boolean;
}) {
  let color = "var(--text-1)";
  if (highlight) color = "var(--accent)";
  if (negative) color = "var(--red)";
  if (positive) color = "var(--green)";

  return (
    <div className="p-3 rounded-lg" style={{ background: "var(--bg-hover)" }}>
      <p className="text-[10px] font-medium tracking-[0.04em] uppercase mb-1" style={{ color: "var(--text-5)" }}>
        {label}
      </p>
      <p className="tnum text-[14px] font-semibold" style={{ color }}>{value}</p>
    </div>
  );
}
