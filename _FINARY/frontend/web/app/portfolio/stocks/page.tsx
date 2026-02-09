"use client";

import { useMemo } from "react";
import { usePortfolio, useDividends, useDiversification } from "@/lib/hooks/useApi";
import { formatEUR, formatPct, formatNumber, pnlColor, CHART_COLORS } from "@/lib/utils";
import { PriceChart } from "@/components/charts/PriceChart";
import { generateNetWorthHistory, generateSparkline } from "@/lib/fixtures";
import { Sparkline } from "@/components/charts/Sparkline";
import { Loading, StatCard } from "@/components/ds";

export default function StocksPage() {
  const { data: positions, isLoading } = usePortfolio();
  const { data: dividends } = useDividends();
  const { data: diversification } = useDiversification();

  const totalValue = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const totalPnl = positions?.reduce((s, p) => s + p.pnl_eur, 0) ?? 0;
  const totalPnlPct = totalValue - totalPnl > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0;

  const chartData = useMemo(() => {
    const hist = generateNetWorthHistory(365);
    return hist.map((h) => ({
      date: h.date,
      value: h.breakdown.investments ?? totalValue,
    }));
  }, [totalValue]);

  const sparklines = useMemo(() => {
    if (!positions) return {};
    const map: Record<string, number[]> = {};
    positions.forEach((p) => {
      map[p.id] = generateSparkline(p.current_price ?? p.avg_cost ?? 100);
    });
    return map;
  }, [positions]);

  const annualDividends = dividends?.reduce((s, d) => s + d.total_amount, 0) ?? 0;
  const dividendYield = totalValue > 0 ? (annualDividends / totalValue) * 100 : 0;

  if (isLoading) return <Loading />;

  return (
    <div className="space-y-6">
      {/* Chart */}
      <div className="card p-6">
        <PriceChart title="Actions & Fonds" data={chartData} color="#5682f2" defaultPeriod="1Y" />
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
      </div>

      {/* Insights row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-4">
          <p className="text-label font-medium mb-2 text-t-5">Fee Scanner</p>
          <div className="flex items-center justify-between">
            <span className="tnum text-heading font-light text-t-1">{formatEUR(totalValue * 0.0099)}</span>
            <span className="tnum text-label text-t-5">/an</span>
          </div>
        </div>

        <div className="card p-4">
          <p className="text-label font-medium mb-2 text-t-5">Diversification</p>
          <div className="flex items-center justify-between">
            <span className="text-body-lg font-medium text-t-1">
              {diversification?.details.num_countries ?? 0} pays
            </span>
            <span className="tnum text-label text-t-4">
              {diversification?.details.num_sectors ?? 0} secteurs
            </span>
          </div>
        </div>

        <div className="card p-4">
          <p className="text-label font-medium mb-2 text-t-5">Dividendes</p>
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
        </div>
      </div>

      {/* Positions table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3 flex items-center justify-between border-b border-bd-1">
          <p className="text-body font-medium text-t-2">Positions</p>
          <p className="text-label text-t-5">{positions?.length ?? 0} actifs</p>
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
                      <p className="text-label text-t-5">{p.ticker} · {p.isin ?? ""}</p>
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
    </div>
  );
}
