"use client";

import { useMemo } from "react";
import { usePortfolio } from "@/lib/hooks/useApi";
import { formatEUR, formatCurrency, formatPct, pnlColor } from "@/lib/utils";
import { Sparkline } from "@/components/charts/Sparkline";
import { generateSparkline } from "@/lib/fixtures";

export default function PortfolioPage() {
  const { data: positions, isLoading, error } = usePortfolio();

  // Generate stable sparklines per position
  const sparklines = useMemo(() => {
    if (!positions) return {};
    const map: Record<string, number[]> = {};
    positions.forEach((p) => {
      map[p.id] = generateSparkline(p.current_price ?? p.avg_cost ?? 100);
    });
    return map;
  }, [positions]);

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  if (error)
    return (
      <div className="text-[13px]" style={{ color: "var(--red)" }}>
        Erreur de connexion API
      </div>
    );

  const totalValue = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const totalPnl = positions?.reduce((s, p) => s + p.pnl_eur, 0) ?? 0;
  const totalPnlPct = totalValue - totalPnl > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-2" style={{ color: "var(--text-5)" }}>
            Investissements
          </p>
          <p className="tnum text-[32px] font-extralight tracking-tight leading-none" style={{ color: "var(--text-1)" }}>
            {formatEUR(totalValue)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`tnum text-[14px] font-medium ${pnlColor(totalPnl)}`}>
            {totalPnl >= 0 ? "+" : ""}{formatEUR(totalPnl)}
          </span>
          <span
            className="tnum text-[11px] font-medium px-2 py-0.5 rounded"
            style={{
              background: totalPnl >= 0 ? "var(--green-bg)" : "var(--red-bg)",
              color: totalPnl >= 0 ? "var(--green)" : "var(--red)",
            }}
          >
            {formatPct(totalPnlPct)}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full text-[13px]">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-1)" }}>
              {["Position", "30j", "Qte", "PRU", "Cours", "Valeur", "+/- value", "Poids"].map((h, i) => (
                <th
                  key={h}
                  className={`${i === 0 ? "text-left pl-5" : "text-right"} px-3 py-3 text-[10px] font-medium tracking-[0.06em] uppercase`}
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
                      style={{
                        background: "var(--bg-hover)",
                        color: "var(--text-3)",
                      }}
                    >
                      {p.ticker.slice(0, 3)}
                    </div>
                    <div>
                      <div className="font-medium" style={{ color: "var(--text-1)" }}>{p.ticker}</div>
                      <div className="text-[11px] mt-0.5 truncate max-w-[140px]" style={{ color: "var(--text-5)" }}>
                        {p.name}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-3 text-right">
                  {sparklines[p.id] ? (
                    <Sparkline data={sparklines[p.id]} />
                  ) : (
                    <span style={{ color: "var(--text-6)" }}>—</span>
                  )}
                </td>
                <td className="tnum text-right px-3 py-3" style={{ color: "var(--text-3)" }}>{p.quantity}</td>
                <td className="tnum text-right px-3 py-3" style={{ color: "var(--text-5)" }}>
                  {p.avg_cost ? formatCurrency(p.avg_cost, p.currency) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3" style={{ color: "var(--text-2)" }}>
                  {p.current_price ? formatCurrency(p.current_price, p.currency) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 font-medium" style={{ color: "var(--text-1)" }}>
                  {formatEUR(p.value_eur)}
                </td>
                <td className={`tnum text-right px-3 py-3 ${pnlColor(p.pnl_eur)}`}>
                  <div className="font-medium">{formatPct(p.pnl_pct)}</div>
                  <div className="text-[11px] opacity-60">
                    {p.pnl_eur >= 0 ? "+" : ""}{formatEUR(p.pnl_eur)}
                  </div>
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
