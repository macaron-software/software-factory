"use client";

import { useMarketSignals } from "@/lib/hooks/useApi";
import { Loading, ErrorState, PageHeader, Badge, Section } from "@/components/ds";
import type { FundamentalsData } from "@/lib/api";

function SignalBadge({ signal }: { signal: "buy" | "hold" | "sell" }) {
  const styles = {
    buy: "bg-green-500/15 text-green-400 border-green-500/30",
    hold: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    sell: "bg-red-500/15 text-red-400 border-red-500/30",
  };
  const labels = { buy: "ACHETER", hold: "CONSERVER", sell: "VENDRE" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold uppercase border ${styles[signal]}`}>
      {labels[signal]}
    </span>
  );
}

function MetricCell({ value, avg, lower_is_better = true }: { value: number | null; avg: number | null; lower_is_better?: boolean }) {
  if (value == null) return <span className="text-t-6">—</span>;
  const formatted = value > 100 ? value.toFixed(0) : value.toFixed(1);
  let color = "text-t-3";
  if (avg && avg > 0) {
    const ratio = value / avg;
    if (lower_is_better) {
      color = ratio < 0.8 ? "text-green-400" : ratio > 1.3 ? "text-red-400" : "text-t-3";
    } else {
      color = ratio > 1.2 ? "text-green-400" : ratio < 0.8 ? "text-red-400" : "text-t-3";
    }
  }
  return (
    <div className="text-right">
      <span className={`tnum font-medium ${color}`}>{formatted}</span>
      {avg != null && <div className="text-[10px] text-t-6 tnum">moy: {avg > 100 ? avg.toFixed(0) : avg.toFixed(1)}</div>}
    </div>
  );
}

function PegCell({ peg, fwd_peg }: { peg: number | null; fwd_peg: number | null }) {
  const val = fwd_peg ?? peg;
  if (val == null || val < 0 || val > 50) return <span className="text-t-6">—</span>;
  const color = val < 1 ? "text-green-400" : val > 2 ? "text-red-400" : "text-t-3";
  return (
    <div className="text-right">
      <span className={`tnum font-medium ${color}`}>{val.toFixed(2)}</span>
      <div className="text-[10px] text-t-6">{val < 1 ? "< 1 🟢" : val > 2 ? "> 2 🔴" : "fair"}</div>
    </div>
  );
}

function SignalRow({ d }: { d: FundamentalsData }) {
  return (
    <tr className="border-b border-bd-1 transition-colors hover:bg-bg-hover">
      <td className="pl-5 px-3 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-caption font-bold shrink-0 bg-bg-hover text-t-3">
            {d.ticker.replace(/\..+/, "").slice(0, 3)}
          </div>
          <div>
            <div className="font-medium text-t-1 flex items-center gap-2">
              {d.ticker}
              {d.in_portfolio && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent/20 text-accent font-semibold">PORTFOLIO</span>
              )}
            </div>
            <div className="text-label mt-0.5 text-t-5">{d.name}</div>
          </div>
        </div>
      </td>
      <td className="px-3 py-3"><SignalBadge signal={d.overall} /></td>
      <td className="px-3 py-3"><MetricCell value={d.pe} avg={d.pe_5y_avg} /></td>
      <td className="px-3 py-3"><PegCell peg={d.peg} fwd_peg={d.fwd_peg} /></td>
      <td className="px-3 py-3"><MetricCell value={d.p_ocf} avg={d.p_ocf_5y_avg} /></td>
      <td className="px-3 py-3"><MetricCell value={d.ev_ebitda} avg={d.ev_ebitda_5y_avg} /></td>
      <td className="px-3 py-3 text-right">
        <span className="tnum text-t-3">{d.div_yield != null && d.div_yield > 0 ? `${d.div_yield.toFixed(2)}%` : "—"}</span>
      </td>
      <td className="px-3 pr-5 py-3">
        <div className="space-y-0.5">
          {d.signals.map((s, i) => (
            <div key={i} className="text-[11px] text-t-5 flex items-center gap-1">
              <span className={s.signal === "buy" ? "text-green-400" : s.signal === "sell" ? "text-red-400" : "text-t-6"}>
                {s.signal === "buy" ? "▲" : s.signal === "sell" ? "▼" : "●"}
              </span>
              {s.reason}
            </div>
          ))}
        </div>
      </td>
    </tr>
  );
}

export default function WatchlistPage() {
  const { data, isLoading, error } = useMarketSignals();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!data) return null;

  const { signals, top_opportunities, updated_at } = data;
  const buyCount = signals.filter((s) => s.overall === "buy").length;
  const portfolioSignals = signals.filter((s) => s.in_portfolio);
  const watchlistSignals = signals.filter((s) => !s.in_portfolio);

  return (
    <div className="space-y-8">
      <PageHeader
        label="Watchlist & Signaux"
        value={0}
        right={
          <div className="flex items-center gap-3">
            <span className="text-t-3 font-medium">{signals.length} titres</span>
            <Badge variant="gain">{buyCount} opportunités</Badge>
            <span className="text-label text-t-6">Màj {new Date(updated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
          </div>
        }
      />

      {/* Top Opportunities */}
      {top_opportunities.length > 0 && (
        <Section title="🎯 Top opportunités">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {top_opportunities.map((d) => (
              <div key={d.ticker} className="card p-4 border border-green-500/20 bg-green-500/5">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-t-1">{d.ticker}</span>
                  <SignalBadge signal="buy" />
                </div>
                <div className="text-label text-t-5 mb-3">{d.name}</div>
                <div className="grid grid-cols-3 gap-2 text-center text-caption">
                  <div>
                    <div className="text-t-6 text-[10px]">PE</div>
                    <div className="tnum text-green-400 font-medium">{d.pe?.toFixed(0) ?? "—"}</div>
                  </div>
                  <div>
                    <div className="text-t-6 text-[10px]">PEG</div>
                    <div className="tnum text-green-400 font-medium">{(d.fwd_peg ?? d.peg)?.toFixed(1) ?? "—"}</div>
                  </div>
                  <div>
                    <div className="text-t-6 text-[10px]">P/OCF</div>
                    <div className="tnum text-green-400 font-medium">{d.p_ocf?.toFixed(0) ?? "—"}</div>
                  </div>
                </div>
                <div className="mt-3 space-y-1">
                  {d.signals.filter((s) => s.signal === "buy").map((s, i) => (
                    <div key={i} className="text-[11px] text-green-400">▲ {s.reason}</div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Portfolio Signals */}
      {portfolioSignals.length > 0 && (
        <Section title="📊 Mes positions">
          <div className="card overflow-hidden">
            <table className="w-full text-body">
              <thead>
                <tr className="border-b border-bd-1">
                  {["Titre", "Signal", "PE", "PEG", "P/OCF", "EV/EBITDA", "Div.", "Analyse"].map((h, i) => (
                    <th key={h} className={`${i === 0 ? "text-left pl-5" : i === 7 ? "text-left" : "text-right"} px-3 py-3 text-caption font-medium uppercase text-t-6`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {portfolioSignals.map((d) => <SignalRow key={d.ticker} d={d} />)}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Watchlist */}
      <Section title="👀 Watchlist">
        <div className="card overflow-hidden">
          <table className="w-full text-body">
            <thead>
              <tr className="border-b border-bd-1">
                {["Titre", "Signal", "PE", "PEG", "P/OCF", "EV/EBITDA", "Div.", "Analyse"].map((h, i) => (
                  <th key={h} className={`${i === 0 ? "text-left pl-5" : i === 7 ? "text-left" : "text-right"} px-3 py-3 text-caption font-medium uppercase text-t-6`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {watchlistSignals.map((d) => <SignalRow key={d.ticker} d={d} />)}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Legend */}
      <div className="text-caption text-t-6 space-y-1 px-1">
        <p>📐 <strong>PE</strong> vs moyenne 5 ans · <strong>PEG</strong> &lt;1 = sous-évalué (Peter Lynch) · <strong>P/OCF</strong> = prix/cash flow opérationnel</p>
        <p>🟢 Vert = ratio &lt; 80% de la moyenne → opportunité · 🔴 Rouge = ratio &gt; 130% → surévalué</p>
        <p>Source: Financial Modeling Prep · Données annuelles (TTM) · Pas une recommandation d&apos;investissement</p>
      </div>
    </div>
  );
}
