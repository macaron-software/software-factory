"use client";

import { useMemo } from "react";
import { usePortfolio, useSparklines, useMarketSignals } from "@/lib/hooks/useApi";
import { formatEUR, formatCurrency, formatPct, pnlColor } from "@/lib/utils";
import { Sparkline } from "@/components/charts/Sparkline";
import { Loading, ErrorState, PageHeader, Badge, Section, SourceBadge } from "@/components/ds";

export default function PortfolioPage() {
  const { data: positions, isLoading, error } = usePortfolio();
  const { data: sparkData } = useSparklines();
  const { data: signalsData } = useMarketSignals();

  const sparklines = useMemo(() => {
    if (!positions || !sparkData) return {};
    const map: Record<string, number[]> = {};
    positions.forEach((p) => {
      const key = p.ticker || p.name;
      if (sparkData[key]) map[p.id] = sparkData[key];
    });
    return map;
  }, [positions, sparkData]);

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
                  <div className="flex items-center justify-end gap-1.5">
                    {p.current_price ? formatCurrency(p.current_price, p.currency) : "—"}
                    {p.live ? <SourceBadge source="live" /> : <SourceBadge source="scraped" />}
                  </div>
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

      {/* Signals Section */}
      {signalsData?.signals && signalsData.signals.filter(s => s.in_portfolio).length > 0 && (
        <Section title="📡 Signaux fondamentaux">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {signalsData.signals.filter(s => s.in_portfolio).map((d) => {
              const signalColors = {
                buy: "border-green-500/30 bg-green-500/5",
                hold: "border-bd-1 bg-bg-1",
                sell: "border-red-500/30 bg-red-500/5",
              };
              const signalLabels = { buy: "ACHETER", hold: "CONSERVER", sell: "VENDRE" };
              const signalBadge = {
                buy: "bg-green-500/15 text-green-400",
                hold: "bg-yellow-500/15 text-yellow-400",
                sell: "bg-red-500/15 text-red-400",
              };
              return (
                <div key={d.ticker} className={`card p-4 border ${signalColors[d.overall]}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-t-1">{d.ticker}</span>
                    <span className={`text-[11px] px-2 py-0.5 rounded font-semibold ${signalBadge[d.overall]}`}>
                      {signalLabels[d.overall]}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-caption mb-2">
                    <div>
                      <div className="text-t-6 text-[10px]">PE</div>
                      <div className="tnum text-t-3">{d.pe?.toFixed(0) ?? "—"}</div>
                      {d.pe_5y_avg && <div className="text-[9px] text-t-6">avg {d.pe_5y_avg.toFixed(0)}</div>}
                    </div>
                    <div>
                      <div className="text-t-6 text-[10px]">PEG</div>
                      <div className="tnum text-t-3">{(d.fwd_peg ?? d.peg) != null && (d.fwd_peg ?? d.peg)! > 0 && (d.fwd_peg ?? d.peg)! < 50 ? (d.fwd_peg ?? d.peg)!.toFixed(1) : "—"}</div>
                    </div>
                    <div>
                      <div className="text-t-6 text-[10px]">P/OCF</div>
                      <div className="tnum text-t-3">{d.p_ocf?.toFixed(0) ?? "—"}</div>
                      {d.p_ocf_5y_avg && <div className="text-[9px] text-t-6">avg {d.p_ocf_5y_avg.toFixed(0)}</div>}
                    </div>
                  </div>
                  <div className="space-y-0.5">
                    {d.signals.map((s, i) => (
                      <div key={i} className="text-[11px] text-t-5">
                        <span className={s.signal === "buy" ? "text-green-400" : s.signal === "sell" ? "text-red-400" : "text-t-6"}>
                          {s.signal === "buy" ? "▲" : s.signal === "sell" ? "▼" : "●"}
                        </span>{" "}
                        {s.reason}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
      )}
    </div>
  );
}
