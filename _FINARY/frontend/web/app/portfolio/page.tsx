"use client";

import { useMemo } from "react";
import { usePortfolio } from "@/lib/hooks/useApi";
import { formatEUR, formatCurrency, formatPct, pnlColor } from "@/lib/utils";
import { Sparkline } from "@/components/charts/Sparkline";
import { generateSparkline } from "@/lib/fixtures";
import { Loading, ErrorState, PageHeader, Badge } from "@/components/ds";

export default function PortfolioPage() {
  const { data: positions, isLoading, error } = usePortfolio();

  const sparklines = useMemo(() => {
    if (!positions) return {};
    const map: Record<string, number[]> = {};
    positions.forEach((p) => {
      map[p.id] = generateSparkline(p.current_price ?? p.avg_cost ?? 100);
    });
    return map;
  }, [positions]);

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;

  const totalValue = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const totalPnl = positions?.reduce((s, p) => s + p.pnl_eur, 0) ?? 0;
  const totalPnlPct = totalValue - totalPnl > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        label="Investissements"
        value={totalValue}
        right={
          <div className="flex items-center gap-2">
            <span className={`tnum text-body-lg font-medium ${pnlColor(totalPnl)}`}>
              {totalPnl >= 0 ? "+" : ""}{formatEUR(totalPnl)}
            </span>
            <Badge variant={totalPnl >= 0 ? "gain" : "loss"}>{formatPct(totalPnlPct)}</Badge>
          </div>
        }
      />

      <div className="card overflow-hidden">
        <table className="w-full text-body">
          <thead>
            <tr className="border-b border-bd-1">
              {["Position", "30j", "Qté", "PRU", "Cours", "Valeur", "+/- value", "Poids"].map((h, i) => (
                <th
                  key={h}
                  className={`${i === 0 ? "text-left pl-5" : "text-right"} px-3 py-3 text-caption font-medium uppercase text-t-6`}
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
                      <div className="font-medium text-t-1">{p.ticker}</div>
                      <div className="text-label mt-0.5 truncate max-w-[140px] text-t-5">{p.name}</div>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-3 text-right">
                  {sparklines[p.id] ? <Sparkline data={sparklines[p.id]} /> : <span className="text-t-6">—</span>}
                </td>
                <td className="tnum text-right px-3 py-3 text-t-3">{p.quantity}</td>
                <td className="tnum text-right px-3 py-3 text-t-5">
                  {p.avg_cost ? formatCurrency(p.avg_cost, p.currency) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 text-t-2">
                  {p.current_price ? formatCurrency(p.current_price, p.currency) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 font-medium text-t-1">{formatEUR(p.value_eur)}</td>
                <td className={`tnum text-right px-3 py-3 ${pnlColor(p.pnl_eur)}`}>
                  <div className="font-medium">{formatPct(p.pnl_pct)}</div>
                  <div className="text-label opacity-60">
                    {p.pnl_eur >= 0 ? "+" : ""}{formatEUR(p.pnl_eur)}
                  </div>
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
