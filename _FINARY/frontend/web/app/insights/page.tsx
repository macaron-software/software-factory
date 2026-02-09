"use client";

import { useMemo } from "react";
import { usePortfolio, useDiversification, useDividends, useCosts, useInsightsRules, useNetWorthHistory } from "@/lib/hooks/useApi";
import { formatEUR, formatPct, formatNumber, CHART_COLORS } from "@/lib/utils";
import { PriceChart } from "@/components/charts/PriceChart";
import { Section, Badge, Loading } from "@/components/ds";

/* ── Simulation helper ── */

function generateSimulation(monthly: number, years: number, annualReturn: number) {
  const data: { year: number; savings: number; returns: number; total: number }[] = [];
  let totalSaved = 0;
  let totalReturns = 0;
  const monthlyRate = annualReturn / 12;
  for (let y = 1; y <= years; y++) {
    for (let m = 0; m < 12; m++) {
      totalSaved += monthly;
      totalReturns += (totalSaved + totalReturns) * monthlyRate;
    }
    data.push({ year: new Date().getFullYear() + y, savings: Math.round(totalSaved), returns: Math.round(totalReturns), total: Math.round(totalSaved + totalReturns) });
  }
  return data;
}

/* ── Score gauge ── */
function ScoreGauge({ score, max, label, detail }: { score: number; max: number; label: string; detail?: string }) {
  const pct = (score / max) * 100;
  const color = score <= 3 ? "var(--red)" : score <= 6 ? "var(--orange)" : "var(--green)";
  const status = score <= 3 ? "Insuffisant" : score <= 6 ? "Moyen" : "Bon";
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-body font-medium text-t-2">{label}</span>
        <span className="tnum text-body font-semibold" style={{ color }}>{status}</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1 bar-track">
          <div className="bar-fill" style={{ width: `${pct}%`, background: color }} />
        </div>
        <span className="tnum text-body font-semibold" style={{ color }}>{score}/{max}</span>
      </div>
      {detail && <p className="text-label mt-2 text-t-5">{detail}</p>}
    </div>
  );
}

/* ── Severity badge colors ── */
const SEVERITY_VARIANT: Record<string, "loss" | "warn" | "accent" | "neutral" | "gain"> = {
  critical: "loss",
  warn: "warn",
  info: "accent",
};

export default function InsightsPage() {
  const { data: positions } = usePortfolio();
  const { data: diversification } = useDiversification();
  const { data: dividends } = useDividends();
  const { data: costs } = useCosts() as { data: any };
  const { data: insights } = useInsightsRules() as { data: any[] | undefined };
  const { data: nwHistory } = useNetWorthHistory(365);

  const totalInvested = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;

  // Real costs from engine (new shape: annual_fees is Record<string, {amount, label, ...}>)
  const costsData = costs as any;
  const annualFeesMap = costsData?.annual_fees as Record<string, { amount: number; label: string; detail?: string; rate_source?: string }> | undefined;
  const totalAnnualFees = costsData?.annual_total ?? 0;
  const feeRate = totalInvested > 0 ? (totalAnnualFees / totalInvested) * 100 : 0;

  const annualDividends = dividends?.reduce((s, d) => s + d.total_amount, 0) ?? 0;
  const dividendYield = totalInvested > 0 ? (annualDividends / totalInvested) * 100 : 0;

  const divData = diversification as any;
  const divScore = divData?.score ?? 4;
  const divMax = divData?.max_score ?? 10;
  const divDetails = divData?.details;
  const divBreakdown = divData?.breakdown;

  const simulation = useMemo(() => generateSimulation(250, 30, 0.07), []);
  const simFinal = simulation[simulation.length - 1];

  const perfData = useMemo(() => {
    if (!nwHistory?.length) return [];
    return nwHistory.map((h: any) => ({
      date: h.date,
      value: h.breakdown?.investments ?? h.net_worth * 0.3,
    }));
  }, [nwHistory]);

  const movers = useMemo(() => {
    if (!positions || positions.length === 0) return [];
    return [...positions]
      .sort((a, b) => Math.abs(b.pnl_pct) - Math.abs(a.pnl_pct))
      .slice(0, 5);
  }, [positions]);

  return (
    <div className="space-y-8">
      <div>
        <p className="text-label font-medium uppercase mb-2 text-t-5">Insights</p>
        <p className="text-[22px] font-light text-t-1">Analyse et recommandations</p>
      </div>

      {/* ── Alerts from rules engine ── */}
      {insights && insights.length > 0 && (
        <Section title="Alertes">
          <div className="space-y-3">
            {insights.map((insight: any, i: number) => (
              <div key={i} className="flex items-start gap-3 py-2">
                <Badge variant={SEVERITY_VARIANT[insight.severity] ?? "neutral"}>
                  {insight.severity === "critical" ? "⚠️" : insight.severity === "warn" ? "⚡" : "ℹ️"} {insight.severity.toUpperCase()}
                </Badge>
                <div className="flex-1">
                  <p className="text-body font-medium text-t-1">{insight.title}</p>
                  <p className="text-label text-t-4 mt-0.5">{insight.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Performance chart */}
      <Section>
        <PriceChart title="Performance" data={perfData} color="#5682f2" defaultPeriod="1Y" />
        <div className="mt-4 pt-4 border-t border-bd-1">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-label mb-1 text-t-5">P&L non réalisé</p>
              <p className="tnum text-title font-medium text-gain">
                {positions ? `+${formatEUR(positions.reduce((s, p) => s + p.pnl_eur, 0))}` : "—"}
              </p>
            </div>
            <div className="text-right">
              <p className="text-label mb-1 text-t-5">Performance</p>
              <p className="tnum text-title font-medium text-gain">
                {positions
                  ? formatPct(
                      (positions.reduce((s, p) => s + p.pnl_eur, 0) /
                        Math.max(1, positions.reduce((s, p) => s + p.value_eur - p.pnl_eur, 0))) *
                        100
                    )
                  : "—"}
              </p>
            </div>
          </div>
        </div>
      </Section>
      {movers.length > 0 && (
        <Section title="My Movers">
          <div className="space-y-0">
            {movers.map((p, i) => (
              <div
                key={p.id}
                className={`flex items-center justify-between py-3 transition-colors ${i < movers.length - 1 ? "border-b border-bd-1" : ""}`}
              >
                <div className="flex items-center gap-3">
                  <span className="tnum text-label font-medium text-t-5">#{i + 1}</span>
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-caption font-bold bg-bg-hover text-t-3">
                    {p.ticker.slice(0, 3)}
                  </div>
                  <div>
                    <p className="text-body font-medium text-t-1">{p.name}</p>
                    <p className="text-label text-t-5">{p.ticker}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="tnum text-body font-medium text-t-1">{formatEUR(p.value_eur)}</p>
                  <p className={`tnum text-label ${p.pnl_eur >= 0 ? "text-gain" : "text-loss"}`}>
                    {p.pnl_eur >= 0 ? "+" : ""}{formatEUR(p.pnl_eur)} ({formatPct(p.pnl_pct)})
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Cards grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Section title="Fee Scanner">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-body text-t-4">Frais estimés</span>
              <span className="tnum text-title font-semibold text-loss">{formatEUR(totalAnnualFees)}/an</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body text-t-4">Taux moyen</span>
              <span className="tnum text-body font-medium text-t-2">{formatNumber(feeRate)}%</span>
            </div>
            <div className="bar-track mt-2">
              <div className="bar-fill bg-loss" style={{ width: `${Math.min(feeRate * 50, 100)}%` }} />
            </div>
            {annualFeesMap && (
              <div className="space-y-1.5 mt-2">
                {Object.values(annualFeesMap).map((fee, i) => (
                  <div key={i} className="flex justify-between text-label">
                    <span className="text-t-5">{fee.label}</span>
                    <span className="text-t-3">{formatEUR(fee.amount)}</span>
                  </div>
                ))}
              </div>
            )}
              {costsData?.potential_savings > 0 ? (
                <p className="text-label text-t-5">
                  TER moyen pondéré vs benchmark 0.20%: économie potentielle {formatEUR(costsData.potential_savings)}/an.
                </p>
              ) : (
                <p className="text-label text-t-5">
                  Frais vérifiés uniquement. Données manquantes: trades IBKR/TR.
                </p>
              )}
          </div>
        </Section>

        <Section title="Revenus passifs">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-body text-t-4">Rendement</span>
              <span className="tnum text-title font-semibold text-gain">{formatNumber(dividendYield)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body text-t-4">Projection (12 mois)</span>
              <span className="tnum text-body font-medium text-t-1">{formatEUR(annualDividends)}</span>
            </div>
            <div className="flex items-end gap-1 h-16 mt-2">
              {["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"].map((m, i) => {
                const h = 10 + Math.random() * 50;
                return (
                  <div key={m} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full rounded-sm" style={{ height: `${h}%`, background: CHART_COLORS[i % 10], opacity: 0.7 }} />
                    <span className="text-[8px] text-t-6">{m.slice(0, 1)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </Section>

        <Section title="Diversification sectorielle">
          <ScoreGauge
            score={divBreakdown?.sectoral?.score ?? divScore}
            max={divBreakdown?.sectoral?.max ?? divMax}
            label="Secteurs"
            detail={`Votre portefeuille couvre ${divDetails?.num_sectors ?? "?"} secteurs. La position ${divDetails?.max_weight_ticker ?? "—"} représente ${formatNumber(divDetails?.max_weight_pct ?? 0)}% du total. Top 3 = ${formatNumber(divDetails?.top3_weight_pct ?? 0)}%.`}
          />
        </Section>

        <Section title="Diversification géographique">
          <ScoreGauge
            score={divBreakdown?.geographic?.score ?? divScore}
            max={divBreakdown?.geographic?.max ?? divMax}
            label="Géographie"
            detail={`Exposé à ${divDetails?.num_countries ?? "?"} pays, ${divDetails?.num_zones ?? "?"} zones (${(divDetails?.zones ?? []).join(", ")}). HHI = ${divDetails?.hhi ?? "?"} (${divData?.rating ?? ""}).`}
          />
        </Section>
      </div>

      {/* Portfolio Simulation */}
      <Section title="Simulation patrimoine">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <p className="text-label mb-1 text-t-5">Mon patrimoine futur</p>
            <p className="tnum text-[24px] font-extralight text-t-1">{formatEUR(simFinal.total)}</p>
            <div className="flex items-end gap-px h-32 mt-4">
              {simulation.map((s, i) => {
                const maxTotal = simFinal.total;
                const h = (s.total / maxTotal) * 100;
                const savingsH = (s.savings / maxTotal) * 100;
                return (
                  <div key={s.year} className="flex-1 flex flex-col items-stretch" style={{ height: "100%" }}>
                    <div className="flex-1" />
                    <div className="rounded-t-sm" style={{ height: `${h - savingsH}%`, background: "var(--chart-4)", opacity: 0.8 }} />
                    <div className="rounded-b-sm" style={{ height: `${savingsH}%`, background: "var(--chart-1)", opacity: 0.6 }} />
                    {i % 5 === 0 && <span className="text-[8px] text-center mt-1 text-t-6">{s.year}</span>}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-3">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm" style={{ background: "var(--chart-1)" }} />
                <span className="text-label text-t-4">Épargne: {formatEUR(simFinal.savings)}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm" style={{ background: "var(--chart-4)" }} />
                <span className="text-label text-t-4">Rendement: {formatEUR(simFinal.returns)}</span>
              </div>
            </div>
          </div>
          <div className="space-y-4">
            <div>
              <p className="text-label mb-1 text-t-5">Épargne mensuelle</p>
              <p className="tnum text-title font-medium text-t-1">250 EUR</p>
            </div>
            <div>
              <p className="text-label mb-1 text-t-5">Durée</p>
              <div className="flex gap-2 mt-1">
                {[10, 20, 30].map((y) => (
                  <span key={y} className={`text-label font-medium px-3 py-1 rounded-md border ${y === 30 ? "bg-bg-3 text-t-1 border-bd-2" : "text-t-5 border-bd-1"}`}>
                    {y} ans
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="text-label mb-1 text-t-5">Rendement annuel</p>
              <p className="tnum text-title font-medium text-t-1">7.00%</p>
            </div>
          </div>
        </div>
      </Section>

      {/* Investor Profile */}
      <Section title="Profil investisseur">
        <div className="grid grid-cols-3 gap-5">
          <div>
            <p className="text-label mb-1 text-t-5">Profil de risque</p>
            <p className="text-body-lg font-semibold text-accent">Long-terme</p>
          </div>
          <div>
            <p className="text-label mb-1 text-t-5">Épargne de précaution</p>
            <p className="text-body-lg font-medium text-t-1">6 mois</p>
          </div>
          <div>
            <p className="text-label mb-1 text-t-5">Taux d&apos;endettement</p>
            <p className="text-body-lg font-medium text-gain">12%</p>
          </div>
        </div>
      </Section>
    </div>
  );
}
