"use client";

import { useMemo } from "react";
import { usePortfolio, useDividends, useDiversification } from "@/lib/hooks/useApi";
import { formatEUR, formatPct, formatNumber, pnlColor, CHART_COLORS } from "@/lib/utils";
import { PriceChart } from "@/components/charts/PriceChart";
import { generateNetWorthHistory, generateSparkline } from "@/lib/fixtures";
import { Sparkline } from "@/components/charts/Sparkline";

export default function StocksPage() {
  const { data: positions, isLoading } = usePortfolio();
  const { data: dividends } = useDividends();
  const { data: diversification } = useDiversification();

  const totalValue = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const totalPnl = positions?.reduce((s, p) => s + p.pnl_eur, 0) ?? 0;
  const totalPnlPct = totalValue - totalPnl > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0;

  // Chart data from investments history
  const chartData = useMemo(() => {
    const hist = generateNetWorthHistory(365);
    return hist.map((h) => ({
      date: h.date,
      value: h.breakdown.investments ?? totalValue,
    }));
  }, [totalValue]);

  // Sparklines
  const sparklines = useMemo(() => {
    if (!positions) return {};
    const map: Record<string, number[]> = {};
    positions.forEach((p) => {
      map[p.id] = generateSparkline(p.current_price ?? p.avg_cost ?? 100);
    });
    return map;
  }, [positions]);

  // Dividends
  const annualDividends = dividends?.reduce((s, d) => s + d.total_amount, 0) ?? 0;
  const dividendYield = totalValue > 0 ? (annualDividends / totalValue) * 100 : 0;

  if (isLoading) return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;

  return (
    <div className="space-y-6">
      {/* Chart */}
      <div className="card p-6">
        <PriceChart title="Actions & Fonds" data={chartData} color="#5682f2" defaultPeriod="1Y" />
        <div className="mt-4 pt-4" style={{ borderTop: "1px solid var(--border-1)" }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] mb-1" style={{ color: "var(--text-5)" }}>P&L Actions & Fonds</p>
              <p className="tnum text-[15px] font-medium" style={{ color: totalPnl >= 0 ? "var(--green)" : "var(--red)" }}>
                {totalPnl >= 0 ? "+" : ""}{formatEUR(totalPnl)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[11px] mb-1" style={{ color: "var(--text-5)" }}>Performance</p>
              <p className="tnum text-[15px] font-medium" style={{ color: totalPnl >= 0 ? "var(--green)" : "var(--red)" }}>
                {formatPct(totalPnlPct)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Insights row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Fee Scanner mini */}
        <div className="card p-4">
          <p className="text-[11px] font-medium mb-2" style={{ color: "var(--text-5)" }}>Fee Scanner</p>
          <div className="flex items-center justify-between">
            <span className="tnum text-[18px] font-light" style={{ color: "var(--text-1)" }}>
              {formatEUR(totalValue * 0.0099)}
            </span>
            <span className="tnum text-[11px]" style={{ color: "var(--text-5)" }}>/an</span>
          </div>
        </div>

        {/* Diversification mini */}
        <div className="card p-4">
          <p className="text-[11px] font-medium mb-2" style={{ color: "var(--text-5)" }}>Diversification</p>
          <div className="flex items-center justify-between">
            <span className="text-[14px] font-medium" style={{ color: "var(--text-1)" }}>
              {diversification?.details.num_countries ?? 0} pays
            </span>
            <span className="tnum text-[11px]" style={{ color: "var(--text-4)" }}>
              {diversification?.details.num_sectors ?? 0} secteurs
            </span>
          </div>
        </div>

        {/* Dividend tracker mini */}
        <div className="card p-4">
          <p className="text-[11px] font-medium mb-2" style={{ color: "var(--text-5)" }}>Dividendes</p>
          <div className="flex items-center justify-between">
            <span className="tnum text-[14px] font-medium" style={{ color: "var(--green)" }}>
              {formatNumber(dividendYield)}% yield
            </span>
            <span className="tnum text-[11px]" style={{ color: "var(--text-4)" }}>
              {formatEUR(annualDividends)} proj.
            </span>
          </div>
          {/* Mini monthly bar */}
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
        <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: "1px solid var(--border-1)" }}>
          <p className="text-[13px] font-medium" style={{ color: "var(--text-2)" }}>Positions</p>
          <p className="text-[11px]" style={{ color: "var(--text-5)" }}>{positions?.length ?? 0} actifs</p>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-1)" }}>
              {["Nom", "30j", "Cours", "Valeur", "P&L", "Poids"].map((h, i) => (
                <th
                  key={h}
                  className={`${i === 0 ? "text-left pl-5" : "text-right"} px-3 py-2.5 text-[10px] font-medium tracking-[0.06em] uppercase`}
                  style={{ color: "var(--text-6)" }}
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
                className="transition-colors cursor-default"
                style={{ borderBottom: "1px solid var(--border-1)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <td className="pl-5 px-3 py-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold shrink-0"
                      style={{ background: "var(--bg-hover)", color: "var(--text-3)" }}
                    >
                      {p.ticker.slice(0, 3)}
                    </div>
                    <div>
                      <p className="font-medium" style={{ color: "var(--text-1)" }}>{p.name}</p>
                      <p className="text-[11px]" style={{ color: "var(--text-5)" }}>{p.ticker} · {p.isin ?? ""}</p>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-3 text-right">
                  {sparklines[p.id] ? <Sparkline data={sparklines[p.id]} /> : <span style={{ color: "var(--text-6)" }}>—</span>}
                </td>
                <td className="tnum text-right px-3 py-3" style={{ color: "var(--text-2)" }}>
                  {p.current_price ? formatEUR(p.current_price) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 font-medium" style={{ color: "var(--text-1)" }}>
                  {formatEUR(p.value_eur)}
                </td>
                <td className={`tnum text-right px-3 py-3 ${pnlColor(p.pnl_eur)}`}>
                  <div>{formatPct(p.pnl_pct)}</div>
                  <div className="text-[11px] opacity-60">{p.pnl_eur >= 0 ? "+" : ""}{formatEUR(p.pnl_eur)}</div>
                </td>
                <td className="tnum text-right px-3 pr-5 py-3" style={{ color: "var(--text-5)" }}>
                  {p.weight_pct.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
