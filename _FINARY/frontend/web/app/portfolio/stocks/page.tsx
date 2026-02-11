"use client";

import { useMemo } from "react";
import { usePortfolio, useDividends, useDiversification, useNetWorthHistory, useSparklines, useCosts } from "@/lib/hooks/useApi";
import { formatEUR, formatPct, formatNumber, pnlColor, CHART_COLORS } from "@/lib/utils";
import { PriceChart } from "@/components/charts/PriceChart";
import { Sparkline } from "@/components/charts/Sparkline";
import { Loading, StatCard, Section } from "@/components/ds";

export default function StocksPage() {
  const { data: positions, isLoading } = usePortfolio();
  const { data: dividends } = useDividends();
  const { data: diversification } = useDiversification();
  const { data: nwHistory } = useNetWorthHistory(365);
  const { data: costs } = useCosts();

  const totalValue = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const totalPnl = positions?.reduce((s, p) => s + p.pnl_eur, 0) ?? 0;
  const totalPnlPct = totalValue - totalPnl > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0;

  const chartData = useMemo(() => {
    if (!nwHistory?.length) return [];
    return nwHistory.map((h: { date: string; breakdown?: { investments?: number }; net_worth: number }) => ({
      date: h.date,
      value: h.breakdown?.investments ?? totalValue,
    }));
  }, [nwHistory, totalValue]);

  const { data: sparkData } = useSparklines();
  const sparklines = useMemo(() => {
    if (!positions || !sparkData) return {};
    const map: Record<string, number[]> = {};
    positions.forEach((p) => {
      const key = p.ticker || p.name;
      if (sparkData[key]) map[p.id] = sparkData[key];
    });
    return map;
  }, [positions, sparkData]);

  const annualDividends = dividends?.reduce((s, d) => s + d.total_amount, 0) ?? 0;
  const dividendYield = totalValue > 0 ? (annualDividends / totalValue) * 100 : 0;

  if (isLoading) return <Loading />;

  return (
    <div className="space-y-8">
      {/* Chart */}
      <Section>
        <PriceChart title="Actions & Fonds" data={chartData} color="#5682f2" defaultPeriod="1Y" liveValue={totalValue} />
        <div className="mt-4 pt-4 border-t border-bd-1">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-label mb-1 text-t-5">P&L Actions & Fonds</p>
              <p className={`tnum text-title font-medium ${totalPnl >= 0 ? "text-gain" : "text-loss"}`}>
                {totalPnl >= 0 ? "+" : ""}{formatEUR(totalPnl)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-label mb-1 text-t-5">Performance</p>
              <p className={`tnum text-title font-medium ${totalPnl >= 0 ? "text-gain" : "text-loss"}`}>
                {formatPct(totalPnlPct)}
              </p>
            </div>
          </div>
        </div>
      </Section>

      {/* Insights row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Section title="Fee Scanner">
          <div className="flex items-center justify-between">
            <span className="tnum text-heading font-light text-t-1">{formatEUR((costs as any)?.annual_total ?? 0)}</span>
            <span className="tnum text-label text-t-5">/an</span>
          </div>
        </Section>

        <Section title="Diversification">
          <div className="flex items-center justify-between">
            <span className="text-body-lg font-medium text-t-1">
              {diversification?.details.num_countries ?? 0} pays
            </span>
            <span className="tnum text-label text-t-4">
              {diversification?.details.num_sectors ?? 0} secteurs
            </span>
          </div>
        </Section>

        <Section title="Dividendes">
          <div className="flex items-center justify-between">
            <span className="tnum text-body-lg font-medium text-gain">
              {formatNumber(dividendYield)}% yield
            </span>
            <span className="tnum text-label text-t-4">{formatEUR(annualDividends)} proj.</span>
          </div>
          <div className="flex items-end gap-px h-8 mt-2">
            {Array.from({ length: 12 }, (_, i) => {
              const h = 20 + Math.random() * 80;
              return <div key={i} className="flex-1 rounded-sm" style={{ height: `${h}%`, background: CHART_COLORS[4], opacity: 0.6 }} />;
            })}
          </div>
        </Section>
      </div>

      {/* Positions table */}
      <Section>
        <div className="-mx-7 -mb-7 overflow-hidden">
        <div className="px-5 py-3 flex items-center justify-between border-b border-bd-1">
          <p className="text-body font-medium text-t-2">Positions</p>
          <div className="flex items-center gap-4">
            {positions && (() => {
              const bySource: Record<string, { count: number; total: number }> = {};
              positions.forEach((p) => {
                const src = (p as any).source ?? "?";
                if (!bySource[src]) bySource[src] = { count: 0, total: 0 };
                bySource[src].count++;
                bySource[src].total += p.value_eur;
              });
              return Object.entries(bySource).map(([src, d]) => (
                <span key={src} className="text-label text-t-5">
                  {src}: <span className="tnum font-medium text-t-3">{formatEUR(d.total)}</span> ({d.count})
                </span>
              ));
            })()}
          </div>
        </div>
        <table className="w-full text-body">
          <thead>
            <tr className="border-b border-bd-1">
              {["Nom", "30j", "Cours", "Valeur", "P&L", "Poids"].map((h, i) => (
                <th
                  key={h}
                  className={`${i === 0 ? "text-left pl-5" : "text-right"} px-3 py-2.5 text-caption font-medium uppercase text-t-6`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions?.map((p) => (
              <tr
                key={p.id}
                className="border-b border-bd-1 transition-colors cursor-default hover:bg-bg-hover"
              >
                <td className="pl-5 px-3 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center text-caption font-bold shrink-0 bg-bg-hover text-t-3">
                      {p.ticker.slice(0, 3)}
                    </div>
                    <div>
                      <p className="font-medium text-t-1">{p.name}</p>
                      <p className="text-label text-t-5">
                        {p.ticker} · {p.isin ?? ""}
                        <span className={`ml-1.5 text-caption font-medium px-1.5 py-0.5 rounded ${(p as any).source === "Trade Republic" ? "bg-accent-bg text-accent" : "bg-warn-bg text-warn"}`}>
                          {(p as any).source === "Trade Republic" ? "TR" : "IBKR"}
                        </span>
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-3 text-right">
                  {sparklines[p.id] ? <Sparkline data={sparklines[p.id]} /> : <span className="text-t-6">—</span>}
                </td>
                <td className="tnum text-right px-3 py-3 text-t-2">
                  {p.current_price ? formatEUR(p.current_price) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 font-medium text-t-1">{formatEUR(p.value_eur)}</td>
                <td className={`tnum text-right px-3 py-3 ${pnlColor(p.pnl_eur)}`}>
                  <div>{formatPct(p.pnl_pct)}</div>
                  <div className="text-label opacity-60">{p.pnl_eur >= 0 ? "+" : ""}{formatEUR(p.pnl_eur)}</div>
                </td>
                <td className="tnum text-right px-3 pr-5 py-3 text-t-5">{p.weight_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </Section>
    </div>
  );
}
