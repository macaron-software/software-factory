"use client";

import { useMemo } from "react";
import { usePortfolio, useDiversification, useDividends } from "@/lib/hooks/useApi";
import { formatEUR, formatPct, formatNumber, CHART_COLORS } from "@/lib/utils";
import { generateNetWorthHistory } from "@/lib/fixtures";
import { PriceChart } from "@/components/charts/PriceChart";
import { Section } from "@/components/ds";

/* ── Fixture generators for insights demo ── */

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
    data.push({
      year: new Date().getFullYear() + y,
      savings: Math.round(totalSaved),
      returns: Math.round(totalReturns),
      total: Math.round(totalSaved + totalReturns),
    });
  }
  return data;
}

const LEADERBOARD = [
  { rank: 1, name: "BNP Paribas Easy S&P 500 UCITS ETF EUR C", ticker: "ESE", pct: "8.05%" },
  { rank: 2, name: "Amundi MSCI World UCITS ETF Acc", ticker: "CW8", pct: "7.21%" },
  { rank: 3, name: "iShares Core MSCI World UCITS ETF", ticker: "IWDA", pct: "6.89%" },
  { rank: 4, name: "Amundi Nasdaq-100 UCITS ETF Acc", ticker: "ANX", pct: "5.54%" },
  { rank: 5, name: "Lyxor MSCI World PEA ETF", ticker: "EWLD", pct: "4.82%" },
  { rank: 6, name: "BNP Paribas Easy STOXX Europe 600", ticker: "ETZ", pct: "3.91%" },
  { rank: 7, name: "Amundi S&P 500 UCITS ETF Acc", ticker: "500", pct: "3.45%" },
  { rank: 8, name: "Amundi MSCI Emerging Markets ETF", ticker: "AEEM", pct: "2.87%" },
];

/* ── Score gauge ── */
function ScoreGauge({ score, max, label }: { score: number; max: number; label: string }) {
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
    </div>
  );
}

export default function InsightsPage() {
  const { data: positions } = usePortfolio();
  const { data: diversification } = useDiversification();
  const { data: dividends } = useDividends();

  const totalInvested = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const estimatedFees = totalInvested * 0.0099;
  const feeRate = 0.99;

  const annualDividends = dividends?.reduce((s, d) => s + d.total_amount, 0) ?? 0;
  const dividendYield = totalInvested > 0 ? (annualDividends / totalInvested) * 100 : 0;

  const divScore = diversification?.score ?? 4;
  const divMax = diversification?.max_score ?? 10;

  const simulation = useMemo(() => generateSimulation(250, 30, 0.07), []);
  const simFinal = simulation[simulation.length - 1];

  const perfData = useMemo(() => {
    const hist = generateNetWorthHistory(365);
    return hist.map((h) => ({
      date: h.date,
      value: h.breakdown.investments ?? h.net_worth * 0.3,
    }));
  }, []);

  const movers = useMemo(() => {
    if (!positions || positions.length === 0) return [];
    return [...positions]
      .sort((a, b) => Math.abs(b.pnl_pct) - Math.abs(a.pnl_pct))
      .slice(0, 5);
  }, [positions]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-label font-medium uppercase mb-2 text-t-5">Insights</p>
        <p className="text-[22px] font-light text-t-1">Analyse et recommandations</p>
      </div>

      {/* Performance chart */}
      <div className="card p-6">
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
      </div>

      {/* My Movers */}
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
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Fee Scanner">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-body text-t-4">Frais estimés</span>
              <span className="tnum text-title font-semibold text-loss">{formatEUR(estimatedFees)}/an</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body text-t-4">Taux moyen</span>
              <span className="tnum text-body font-medium text-t-2">{feeRate}%</span>
            </div>
            <div className="bar-track mt-2">
              <div className="bar-fill bg-loss" style={{ width: `${Math.min(feeRate * 50, 100)}%` }} />
            </div>
            <p className="text-label text-t-5">
              Les frais moyens des ETF sont de 0.20%. Vous pourriez économiser {formatEUR(estimatedFees * 0.8)}/an.
            </p>
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
          <ScoreGauge score={divScore} max={divMax} label="Secteurs" />
          <p className="text-label mt-3 text-t-5">
            Votre portefeuille est concentré sur {diversification?.details.num_sectors ?? 3} secteurs.
            La position {diversification?.details.max_weight_ticker ?? "—"} représente {formatNumber(diversification?.details.max_weight_pct ?? 0)}% du total.
          </p>
        </Section>

        <Section title="Diversification géographique">
          <ScoreGauge score={Math.min(divScore + 1, divMax)} max={divMax} label="Géographie" />
          <p className="text-label mt-3 text-t-5">
            Vous êtes exposé à {diversification?.details.num_countries ?? 2} pays.
            Diversifiez vers les marchés émergents et l&apos;Asie pour améliorer votre score.
          </p>
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
                    {i % 5 === 0 && (
                      <span className="text-[8px] text-center mt-1 text-t-6">{s.year}</span>
                    )}
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
                  <span
                    key={y}
                    className={`text-label font-medium px-3 py-1 rounded-md border ${
                      y === 30 ? "bg-bg-3 text-t-1 border-bd-2" : "text-t-5 border-bd-1"
                    }`}
                  >
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

      {/* Leaderboard */}
      <Section title="Leaderboard">
        <div className="flex items-center gap-3 mb-4">
          {["ETF", "Actions", "Crypto", "SCPI"].map((tab, i) => (
            <button
              key={tab}
              className={`text-label font-medium px-3 py-1.5 rounded-md transition-colors ${
                i === 0 ? "bg-bg-3 text-t-1" : "text-t-5 hover:bg-bg-hover"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="space-y-0">
          {LEADERBOARD.map((item, i) => (
            <div
              key={item.rank}
              className={`flex items-center justify-between py-2.5 transition-colors ${i < LEADERBOARD.length - 1 ? "border-b border-bd-1" : ""}`}
            >
              <div className="flex items-center gap-3">
                <span className={`tnum text-label font-semibold w-6 ${item.rank <= 3 ? "text-accent" : "text-t-5"}`}>
                  #{item.rank}
                </span>
                <div className="w-7 h-7 rounded-md flex items-center justify-center text-[9px] font-bold bg-bg-hover text-t-3">
                  {item.ticker}
                </div>
                <div>
                  <p className="text-label font-medium truncate max-w-[280px] text-t-1">{item.name}</p>
                  <p className="text-caption text-t-5">EUR</p>
                </div>
              </div>
              <span className="tnum text-label font-medium text-t-4">{item.pct} utilisateurs</span>
            </div>
          ))}
        </div>
      </Section>

      {/* Investor Profile */}
      <Section title="Profil investisseur">
        <div className="grid grid-cols-3 gap-4">
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
