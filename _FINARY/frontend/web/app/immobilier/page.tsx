"use client";

import { useSCA } from "@/lib/hooks/useApi";
import { formatEUR, formatEURCompact, formatNumber, CHART_COLORS } from "@/lib/utils";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { Loading, ErrorState, PageHeader, Badge, Section, StatCard, SourceBadge } from "@/components/ds";

export default function ImmobilierPage() {
  const { data: sca, isLoading, error } = useSCA();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!sca) return null;

  const prop = sca.property;
  const fin = sca.financials;
  const market = sca.market;
  // Gain = market median value vs total invested (construction cost)
  const constructionCost = sca.your_share_construction_cost ?? fin.total_verse;
  const gainPct = constructionCost > 0
    ? ((sca.your_share_property_value - constructionCost) / constructionCost * 100) : 0;
  const gainEur = sca.your_share_property_value - constructionCost;

  const ownershipData = [
    { name: "Votre part", value: sca.ownership_pct },
    { name: sca.co_associate.name, value: sca.co_associate.ownership_pct },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        label={`Immobilier — ${sca.name}`}
        value={sca.your_share_property_value}
        right={
          <div className="flex items-center gap-2">
            <span className={`num-inline ${gainEur >= 0 ? "text-gain" : "text-loss"}`}>
              {gainEur >= 0 ? "+" : ""}{formatEURCompact(gainEur)}
            </span>
            <Badge variant={gainEur >= 0 ? "gain" : "loss"}>
              {gainPct >= 0 ? "+" : ""}{gainPct.toFixed(1)}%
            </Badge>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Valuation summary */}
        <Section title="Valorisation — votre maison (118m²)">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-label text-t-5">Médiane neuf</span>
              <div className="flex items-center gap-2">
                <span className="num-inline text-accent">{formatEURCompact(sca.your_house_market_neuf ?? sca.your_share_property_value)}</span>
                <SourceBadge source="estimate" />
              </div>
            </div>
            <p className="text-source text-right -mt-2">4 100€/m² × 118m² · MeilleursAgents</p>
            <div className="flex items-center justify-between">
              <span className="text-label text-t-5">Médiane ancien</span>
              <span className="num-inline text-t-3">{formatEURCompact(sca.your_house_market_ancien ?? 0)}</span>
            </div>
            <p className="text-source text-right -mt-2">3 530€/m² × 118m²</p>
            <div className="flex items-center justify-between">
              <span className="text-label text-t-5">Estimation Bourso</span>
              <div className="flex items-center gap-2">
                <span className="num-inline text-t-2">{formatEURCompact(sca.your_share_bourso_estimate ?? 0)}</span>
                <SourceBadge source="scraped" />
              </div>
            </div>
            <div className="pt-3 mt-3 border-t border-bd-1">
              <div className="flex items-center justify-between">
                <span className="text-label text-t-5">Coût construction</span>
                <span className="num-inline text-t-4">{formatEURCompact(constructionCost)}</span>
              </div>
              <p className="text-source text-right mt-0.5">Capital versé + avances CCA</p>
            </div>
            <div className="pt-3 mt-3 border-t border-bd-1">
              <div className="flex items-center justify-between">
                <span className="text-label font-medium text-t-3">Plus-value latente</span>
                <span className={`num-inline font-semibold ${gainEur >= 0 ? "text-gain" : "text-loss"}`}>
                  {gainEur >= 0 ? "+" : ""}{formatEURCompact(gainEur)} ({gainPct >= 0 ? "+" : ""}{gainPct.toFixed(1)}%)
                </span>
              </div>
              <p className="text-source text-right mt-0.5">Neuf vs investissement</p>
            </div>
          </div>
        </Section>

        {/* Property card */}
        <Section title="Propriété">
          <div className="space-y-3">
            <InfoRow label="Adresse" value={prop.address} />
            <InfoRow label="Type" value={`${prop.type} — ${prop.rooms} pièces`} />
            <InfoRow label="Surface habitable" value={`${prop.surface_m2} m²`} />
            {prop.terrain_privatif_m2 && <InfoRow label="Terrain privatif" value={`${prop.terrain_privatif_m2} m²`} />}
            {prop.terrain_commun_m2 && <InfoRow label="Terrain commun" value={`${prop.terrain_commun_m2} m²`} />}
            <InfoRow label="DPE" value={prop.dpe_score} />
            <InfoRow label="Date d'achat" value={prop.purchase_date} />
            <InfoRow label="Prix/m² estimé" value={formatEURCompact(prop.price_per_m2_estimate)} />
            <div className="pt-3 mt-3 border-t border-bd-1">
              <InfoRow label="Estimation Bourso" value={formatEURCompact(prop.bourso_estimate)} highlight />
              <p className="text-detail mt-1 text-right">
                {formatEURCompact(prop.bourso_estimate_range.low)} — {formatEURCompact(prop.bourso_estimate_range.high)}
              </p>
            </div>
          </div>
        </Section>

        {/* Ownership chart */}
        <Section title="Répartition SCA">
          <div className="flex items-center gap-6">
            <div className="w-[140px] h-[140px] shrink-0 relative">
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-[1]">
                <span className="num-stat text-t-1">
                  {sca.ownership_pct.toFixed(1)}%
                </span>
                <span className="text-source">Votre part</span>
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

      {/* Grabels Market Data */}
      {market && (
        <>
          <Section title={`Marché immobilier — ${market.commune} (${market.code_postal})`}>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
              <StatCard
                label="Prix achat /m² (maison)"
                value={market.prix_m2_achat.maison.median}
                detail={`${formatEUR(market.prix_m2_achat.maison.low)} — ${formatEUR(market.prix_m2_achat.maison.high)}`}
              />
              <StatCard
                label="Loyer /m² mensuel"
                value={market.loyer_m2.median}
                detail={`${market.loyer_m2.low}€ — ${market.loyer_m2.high}€`}
              />
              <StatCard
                label="Construction /m²"
                value={market.cout_construction_m2.standard.low}
                detail={`${formatEUR(market.cout_construction_m2.standard.low)} — ${formatEUR(market.cout_construction_m2.standard.high)}`}
              />
              <StatCard
                label="Rendement locatif brut"
                value={market.rendement_locatif_brut_pct}
                detail="Basé sur loyer médian"
                tone={market.rendement_locatif_brut_pct >= 4 ? "positive" : "accent"}
              />
            </div>
            <p className="text-source mt-3">
              Sources : {market.prix_m2_achat.source} · {market.loyer_m2.source} · {market.cout_construction_m2.source} — {market.date_source}
            </p>
          </Section>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Section title={`Estimation revente (${prop.surface_m2} m²)`}>
              <div className="space-y-3">
                <InfoRow label="Fourchette basse" value={formatEURCompact(market.estimation_revente.low)} />
                <InfoRow label="Médiane ancien" value={formatEURCompact(market.estimation_revente.median_ancien ?? market.estimation_revente.median ?? 0)} />
                <InfoRow label="Médiane neuf" value={formatEURCompact(market.estimation_revente.median_neuf ?? 0)} />
                <InfoRow label="Fourchette haute" value={formatEURCompact(market.estimation_revente.high)} />
                <div className="pt-3 mt-3 border-t border-bd-1">
                  <InfoRow label="Estimation Bourso" value={formatEURCompact(market.estimation_revente.bourso)} highlight />
                </div>
                <div className="mt-2">
                  <PriceBar
                    low={market.estimation_revente.low}
                    high={market.estimation_revente.high}
                    current={market.estimation_revente.bourso}
                    label="Bourso"
                  />
                </div>
              </div>
            </Section>

            <Section title="Loyer mensuel estimé">
              <div className="space-y-3">
                <InfoRow label="Bas" value={`${formatEUR(market.estimation_loyer_mensuel.low)}/mois`} />
                <InfoRow label="Médian" value={`${formatEUR(market.estimation_loyer_mensuel.median)}/mois`} />
                <InfoRow label="Haut" value={`${formatEUR(market.estimation_loyer_mensuel.high)}/mois`} />
                <div className="pt-3 mt-3 border-t border-bd-1">
                  <InfoRow label="Revenu annuel (médian)" value={formatEURCompact(market.estimation_loyer_mensuel.median * 12)} highlight />
                </div>
              </div>
            </Section>

            <Section title="Coût de reconstruction">
              <div className="space-y-3">
                <InfoRow label="Économique" value={formatEURCompact(market.cout_reconstruction.economique)} />
                <InfoRow label="Standard" value={formatEURCompact(market.cout_reconstruction.standard)} />
                <InfoRow label="Contemporain" value={formatEURCompact(market.cout_reconstruction.contemporain)} />
                <div className="pt-3 mt-3 border-t border-bd-1">
                  <div className="flex items-center justify-between">
                    <span className="text-label text-t-5">Valeur terrain (bilan)</span>
                    <span className="num-inline text-accent">{formatEURCompact(prop.terrain_value_book)}</span>
                  </div>
                </div>
              </div>
            </Section>
          </div>
        </>
      )}

      {/* Financial details */}
      <Section title="Situation financière SCA">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
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
      <span className={`num-inline ${highlight ? "text-accent" : "text-t-1"}`}>
        {value}
      </span>
    </div>
  );
}

/* Visual bar showing where the current price sits in a range */
function PriceBar({ low, high, current, label }: { low: number; high: number; current: number; label: string }) {
  const range = high - low;
  const pos = range > 0 ? Math.min(100, Math.max(0, ((current - low) / range) * 100)) : 50;
  return (
    <div>
      <div className="relative h-2 rounded-full bg-bg-hover">
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-accent border-2 border-bg-1"
          style={{ left: `${pos}%`, transform: `translate(-50%, -50%)` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-source">{formatEURCompact(low)}</span>
        <span className="text-caption font-medium text-accent">{label}</span>
        <span className="text-source">{formatEURCompact(high)}</span>
      </div>
    </div>
  );
}
