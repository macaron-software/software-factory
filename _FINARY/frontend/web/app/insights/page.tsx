"use client";

import { useMemo, useState } from "react";
import { usePortfolio, useDiversification, useDividends, useCosts, useInsightsRules, useNetWorthHistory, useNetWorth } from "@/lib/hooks/useApi";
import { formatEUR, formatPct, formatNumber, CHART_COLORS } from "@/lib/utils";
import { PriceChart } from "@/components/charts/PriceChart";
import { Section, Badge, Loading, SourceBadge } from "@/components/ds";

/* ── Simulation helper ── */

function generateSimulation(startingCapital: number, monthly: number, years: number, annualReturn: number, inflation: number) {
  const data: { year: number; savings: number; returns: number; total: number; totalReal: number }[] = [];
  let totalSaved = startingCapital;
  let totalReturns = 0;
  const monthlyRate = annualReturn / 12;
  const inflationMonthly = inflation / 12;
  // Real terms: deflate by cumulative inflation
  let cumulInflation = 1;
  for (let y = 1; y <= years; y++) {
    for (let m = 0; m < 12; m++) {
      totalReturns += (totalSaved + totalReturns) * monthlyRate;
      totalSaved += monthly;
      cumulInflation *= (1 + inflationMonthly);
    }
    const nominal = totalSaved + totalReturns;
    data.push({
      year: new Date().getFullYear() + y,
      savings: Math.round(totalSaved),
      returns: Math.round(totalReturns),
      total: Math.round(nominal),
      totalReal: Math.round(nominal / cumulInflation),
    });
  }
  return data;
}

/* ── Score gauge ── */
function ScoreGauge({ score, max, label, detail }: { score: number; max: number; label: string; detail?: string }) {
  const pct = (score / max) * 100;
  const color = score <= 3 ? "var(--red)" : score <= 6 ? "var(--orange)" : "var(--green)";
  const status = score <= 3 ? "Insuffisant" : score <= 6 ? "Moyen" : "Correct";
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

/* ── Mini horizontal bar ── */
function HBar({ items, maxValue }: { items: { label: string; value: number; pct: number; color: string }[]; maxValue?: number }) {
  const mx = maxValue ?? Math.max(...items.map(i => i.pct));
  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div key={i}>
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-label text-t-3 truncate">{item.label}</span>
            <span className="tnum text-label text-t-4 ml-2 shrink-0">{formatNumber(item.pct)}%</span>
          </div>
          <div className="bar-track" style={{ height: 6 }}>
            <div className="bar-fill" style={{ width: `${(item.pct / mx) * 100}%`, background: item.color, opacity: 0.8 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Mini donut SVG ── */
function MiniDonut({ segments }: { segments: { pct: number; color: string; label: string }[] }) {
  const r = 40, cx = 50, cy = 50, stroke = 14;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg viewBox="0 0 100 100" className="w-28 h-28 shrink-0">
      {segments.map((s, i) => {
        const dash = (s.pct / 100) * circ;
        const gap = circ - dash;
        const el = (
          <circle
            key={i} cx={cx} cy={cy} r={r}
            fill="none" stroke={s.color} strokeWidth={stroke}
            strokeDasharray={`${dash} ${gap}`}
            strokeDashoffset={-offset}
            style={{ transform: "rotate(-90deg)", transformOrigin: "center" }}
          />
        );
        offset += dash;
        return el;
      })}
    </svg>
  );
}

/* ── Severity badge colors ── */
const SEVERITY_VARIANT: Record<string, "loss" | "warn" | "accent" | "neutral" | "gain"> = {
  critical: "loss",
  warn: "warn",
  info: "accent",
};

const SECTOR_COLORS: Record<string, string> = {
  "Technology": "#5682f2",
  "Semiconductors": "#8b5cf6",
  "Healthcare": "#10b981",
  "Energy": "#f59e0b",
  "Consumer": "#ec4899",
  "Automotive": "#06b6d4",
  "Luxury": "#d946ef",
  "Finance": "#3b82f6",
  "Real Estate": "#14b8a6",
  "Industrials": "#64748b",
  "Defense": "#6366f1",
  "Other": "#94a3b8",
};

const ZONE_COLORS: Record<string, string> = {
  "Amérique du Nord": "#5682f2",
  "Europe": "#10b981",
  "Asie": "#f59e0b",
  "Amérique Latine": "#ec4899",
  "Autre": "#94a3b8",
};

export default function InsightsPage() {
  const { data: positions } = usePortfolio();
  const { data: diversification } = useDiversification();
  const { data: dividends } = useDividends();
  const { data: costs } = useCosts() as { data: any };
  const { data: insights } = useInsightsRules() as { data: any[] | undefined };
  const { data: nwHistory } = useNetWorthHistory(365);
  const { data: netWorthData } = useNetWorth();

  const [simYears, setSimYears] = useState(20);
  const [simMonthly, setSimMonthly] = useState(250);
  const [simReturn, setSimReturn] = useState(7);
  const [showRealTerms, setShowRealTerms] = useState(false);
  const [expandedSector, setExpandedSector] = useState<string | null>(null);
  const [expandedCountry, setExpandedCountry] = useState<string | null>(null);

  const totalInvested = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const currentNetWorth = netWorthData?.net_worth ?? 0;
  const INFLATION = 0.024;

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
  const suggestions = divData?.suggestions ?? [];

  const simulation = useMemo(
    () => generateSimulation(currentNetWorth, simMonthly, simYears, simReturn / 100, INFLATION),
    [currentNetWorth, simMonthly, simYears, simReturn]
  );
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

  // Sector/Zone data for charts
  const sectorsDetail: any[] = divBreakdown?.sectoral?.detail ?? [];
  const zonesDetail: any[] = divBreakdown?.geographic?.zones_detail ?? [];
  const countriesDetail: any[] = divBreakdown?.geographic?.countries_detail ?? [];
  const topPositions: any[] = divBreakdown?.concentration?.top_positions ?? [];

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

      {/* ── Diversification suggestions ── */}
      {suggestions.length > 0 && (
        <Section title="Recommandations diversification">
          <div className="space-y-3">
            {suggestions.map((s: any, i: number) => (
              <div key={i} className="flex items-start gap-3 py-2">
                <Badge variant={SEVERITY_VARIANT[s.severity] ?? "neutral"}>
                  {s.severity === "critical" ? "🔴" : s.severity === "warn" ? "🟡" : "🔵"}
                </Badge>
                <p className="text-body text-t-2 flex-1">{s.reason}</p>
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

      {/* Cards grid — Fee Scanner + Dividends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Section title={<>Fee Scanner <SourceBadge source="computed" /></>}>
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

        <Section title={<>Revenus passifs <SourceBadge source="hardcoded" /></>}>
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
      </div>

      {/* ══ DIVERSIFICATION — DEEP ANALYSIS ══ */}

      {/* Overall score */}
      <Section title={<>Diversification <SourceBadge source="computed" /></>}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <ScoreGauge
            score={divBreakdown?.concentration?.score ?? 0}
            max={divBreakdown?.concentration?.max ?? 4}
            label="Concentration"
            detail={`HHI = ${divDetails?.hhi ?? "?"}. Top 1 = ${divDetails?.max_weight_pct ?? 0}%, Top 3 = ${divDetails?.top3_weight_pct ?? 0}%.`}
          />
          <ScoreGauge
            score={divBreakdown?.sectoral?.score ?? 0}
            max={divBreakdown?.sectoral?.max ?? 3}
            label="Secteurs"
            detail={`${divDetails?.num_sectors ?? "?"} secteurs couverts. HHI sectoriel = ${divBreakdown?.sectoral?.hhi ?? "?"}.`}
          />
          <ScoreGauge
            score={divBreakdown?.geographic?.score ?? 0}
            max={divBreakdown?.geographic?.max ?? 3}
            label="Géographie"
            detail={`${divDetails?.num_zones ?? "?"} zones, ${divDetails?.num_countries ?? "?"} pays. HHI zones = ${divBreakdown?.geographic?.hhi ?? "?"}.`}
          />
        </div>
        <div className="mt-4 pt-4 border-t border-bd-1 flex items-center justify-between">
          <span className="text-body text-t-3">Score global</span>
          <span className="tnum text-title font-semibold" style={{ color: divScore <= 3 ? "var(--red)" : divScore <= 6 ? "var(--orange)" : "var(--green)" }}>
            {divScore}/{divMax} — {divData?.rating ?? ""}
          </span>
        </div>
      </Section>

      {/* Concentration — Top positions */}
      <Section title="Concentration — Top positions">
        <div className="flex items-start gap-6">
          <MiniDonut
            segments={topPositions.slice(0, 5).map((p: any, i: number) => ({
              pct: p.weight_pct,
              color: CHART_COLORS[i % CHART_COLORS.length],
              label: p.ticker,
            })).concat(
              topPositions.length > 5 ? [{
                pct: 100 - topPositions.slice(0, 5).reduce((s: number, p: any) => s + p.weight_pct, 0),
                color: "#334155",
                label: "Autres",
              }] : []
            )}
          />
          <div className="flex-1 space-y-2">
            {topPositions.slice(0, 7).map((p: any, i: number) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                <span className="text-label font-medium text-t-2 w-16 truncate">{p.ticker}</span>
                <div className="flex-1 bar-track" style={{ height: 4 }}>
                  <div className="bar-fill" style={{ width: `${p.weight_pct}%`, background: CHART_COLORS[i % CHART_COLORS.length] }} />
                </div>
                <span className="tnum text-label text-t-4 w-12 text-right">{formatNumber(p.weight_pct)}%</span>
                <span className="tnum text-label text-t-5 w-20 text-right">{formatEUR(p.value_eur)}</span>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Sectors + Geography side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Sectoral breakdown */}
        <Section title={`Répartition sectorielle (${sectorsDetail.length} secteurs)`}>
          <div className="flex items-start gap-5">
            <MiniDonut
              segments={sectorsDetail.slice(0, 6).map((s: any) => ({
                pct: s.weight_pct,
                color: SECTOR_COLORS[s.name] ?? "#94a3b8",
                label: s.name,
              }))}
            />
            <div className="flex-1 space-y-1.5">
              {sectorsDetail.map((s: any, i: number) => (
                <div key={i}>
                  <div
                    className="flex items-center justify-between py-1 cursor-pointer rounded px-1 -mx-1 hover:bg-bg-hover"
                    onClick={() => setExpandedSector(expandedSector === s.name ? null : s.name)}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-sm" style={{ background: SECTOR_COLORS[s.name] ?? "#94a3b8" }} />
                      <span className="text-label text-t-2">{s.name}</span>
                      <span className="text-label text-t-5">({s.positions.length})</span>
                    </div>
                    <span className="tnum text-label text-t-3">{formatNumber(s.weight_pct)}%</span>
                  </div>
                  {expandedSector === s.name && (
                    <div className="ml-5 mb-2 space-y-1 border-l-2 pl-3" style={{ borderColor: SECTOR_COLORS[s.name] ?? "#94a3b8" }}>
                      {s.positions.map((p: any, j: number) => (
                        <div key={j} className="flex justify-between text-label">
                          <span className="text-t-4">{p.ticker}</span>
                          <span className="tnum text-t-5">{formatEUR(p.value_eur)} ({formatNumber(p.weight_pct)}%)</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </Section>

        {/* Geographic breakdown */}
        <Section title={`Répartition géographique (${countriesDetail.length} pays)`}>
          <div className="flex items-start gap-5">
            <MiniDonut
              segments={zonesDetail.map((z: any) => ({
                pct: z.weight_pct,
                color: ZONE_COLORS[z.name] ?? "#94a3b8",
                label: z.name,
              }))}
            />
            <div className="flex-1 space-y-2">
              {zonesDetail.map((z: any, i: number) => (
                <div key={i}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-sm" style={{ background: ZONE_COLORS[z.name] ?? "#94a3b8" }} />
                      <span className="text-label font-medium text-t-2">{z.name}</span>
                    </div>
                    <span className="tnum text-label text-t-3">{formatNumber(z.weight_pct)}%</span>
                  </div>
                  {/* Countries in this zone */}
                  <div className="ml-5 space-y-1">
                    {countriesDetail.filter((c: any) => c.zone === z.name).map((c: any, j: number) => (
                      <div key={j}>
                        <div
                          className="flex justify-between text-label cursor-pointer hover:text-t-2 py-0.5 px-1 -mx-1 rounded hover:bg-bg-hover"
                          onClick={() => setExpandedCountry(expandedCountry === c.code ? null : c.code)}
                        >
                          <span className="text-t-4">{c.name}</span>
                          <span className="tnum text-t-5">{formatNumber(c.weight_pct)}%</span>
                        </div>
                        {expandedCountry === c.code && (
                          <div className="ml-3 mb-1 space-y-0.5 border-l pl-2" style={{ borderColor: ZONE_COLORS[z.name] ?? "#94a3b8" }}>
                            {c.positions.map((p: any, k: number) => (
                              <div key={k} className="flex justify-between text-label">
                                <span className="text-t-5">{p.ticker}</span>
                                <span className="tnum text-t-6">{formatEUR(p.value_eur)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Section>
      </div>

      {/* ══ SIMULATION PATRIMOINE ══ */}
      <Section title={<>Simulation patrimoine <SourceBadge source="computed" /></>}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <p className="text-label mb-1 text-t-5">Mon patrimoine futur {showRealTerms ? "(€ constants)" : "(nominal)"}</p>
            <p className="tnum text-[24px] font-extralight text-t-1">
              {formatEUR(showRealTerms ? simFinal.totalReal : simFinal.total)}
            </p>
            <p className="tnum text-label text-t-5 mt-0.5">
              Départ: {formatEUR(currentNetWorth)}
              {showRealTerms && ` · Pouvoir d'achat réel (inflation ${(INFLATION * 100).toFixed(1)}%)`}
            </p>
            <div className="flex items-end gap-px h-32 mt-4">
              {simulation.map((s, i) => {
                const maxTotal = showRealTerms ? simFinal.totalReal : simFinal.total;
                const val = showRealTerms ? s.totalReal : s.total;
                const h = maxTotal > 0 ? (val / maxTotal) * 100 : 0;
                const startPct = maxTotal > 0 ? (currentNetWorth / maxTotal) * 100 : 0;
                const savingsPct = maxTotal > 0 ? ((s.savings - currentNetWorth) / maxTotal) * 100 : 0;
                const returnsPct = h - startPct - Math.max(0, savingsPct);
                return (
                  <div key={s.year} className="flex-1 flex flex-col items-stretch" style={{ height: "100%" }}>
                    <div className="flex-1" />
                    <div className="rounded-t-sm" style={{ height: `${Math.max(0, returnsPct)}%`, background: "var(--chart-4)", opacity: 0.8 }} />
                    <div style={{ height: `${Math.max(0, savingsPct)}%`, background: "var(--chart-1)", opacity: 0.6 }} />
                    <div className="rounded-b-sm" style={{ height: `${Math.max(0, startPct)}%`, background: "var(--chart-2)", opacity: 0.4 }} />
                    {i % Math.max(1, Math.floor(simulation.length / 6)) === 0 && <span className="text-[8px] text-center mt-1 text-t-6">{s.year}</span>}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-3 flex-wrap">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm" style={{ background: "var(--chart-2)", opacity: 0.4 }} />
                <span className="text-label text-t-4">Capital initial: {formatEUR(currentNetWorth)}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm" style={{ background: "var(--chart-1)" }} />
                <span className="text-label text-t-4">Épargne: {formatEUR(simFinal.savings - currentNetWorth)}</span>
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
              <div className="flex items-center gap-2">
                {[100, 250, 500, 1000].map((v) => (
                  <button
                    key={v}
                    className={`text-label font-medium px-2 py-1 rounded-md border transition-colors ${v === simMonthly ? "bg-bg-3 text-t-1 border-bd-2" : "text-t-5 border-bd-1 hover:border-bd-2"}`}
                    onClick={() => setSimMonthly(v)}
                  >
                    {v}€
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-label mb-1 text-t-5">Durée</p>
              <div className="flex gap-2">
                {[10, 20, 30].map((y) => (
                  <button
                    key={y}
                    className={`text-label font-medium px-3 py-1 rounded-md border transition-colors ${y === simYears ? "bg-bg-3 text-t-1 border-bd-2" : "text-t-5 border-bd-1 hover:border-bd-2"}`}
                    onClick={() => setSimYears(y)}
                  >
                    {y} ans
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-label mb-1 text-t-5">Rendement annuel</p>
              <div className="flex items-center gap-2">
                {[5, 7, 10].map((r) => (
                  <button
                    key={r}
                    className={`text-label font-medium px-2 py-1 rounded-md border transition-colors ${r === simReturn ? "bg-bg-3 text-t-1 border-bd-2" : "text-t-5 border-bd-1 hover:border-bd-2"}`}
                    onClick={() => setSimReturn(r)}
                  >
                    {r}%
                  </button>
                ))}
              </div>
            </div>
            <div>
              <button
                className={`text-label font-medium px-3 py-1.5 rounded-md border transition-colors ${showRealTerms ? "bg-bg-3 text-t-1 border-bd-2" : "text-t-5 border-bd-1 hover:border-bd-2"}`}
                onClick={() => setShowRealTerms(!showRealTerms)}
              >
                {showRealTerms ? "📉 € constants (réel)" : "📈 € nominaux"}
              </button>
              <p className="text-label text-t-6 mt-1">Inflation: {(INFLATION * 100).toFixed(1)}%/an</p>
            </div>
            {/* Key projections */}
            <div className="border-t border-bd-1 pt-3 space-y-1.5">
              <div className="flex justify-between text-label">
                <span className="text-t-5">Rendement cumulé</span>
                <span className="tnum text-gain">{formatEUR(simFinal.returns)}</span>
              </div>
              <div className="flex justify-between text-label">
                <span className="text-t-5">Effet levier composé</span>
                <span className="tnum text-t-2">×{(simFinal.total / (simFinal.savings)).toFixed(1)}</span>
              </div>
              {showRealTerms && (
                <div className="flex justify-between text-label">
                  <span className="text-t-5">Perte inflation</span>
                  <span className="tnum text-loss">-{formatEUR(simFinal.total - simFinal.totalReal)}</span>
                </div>
              )}
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
