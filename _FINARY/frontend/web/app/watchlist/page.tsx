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

/** Mini SVG sparkline — 60×20px, no deps */
function Sparkline({ values, avg, lower_is_better = true }: { values: (number | null)[]; avg?: number | null; lower_is_better?: boolean }) {
  const pts = values.filter((v): v is number => v != null && v > 0);
  if (pts.length < 2) return <span className="text-t-6 text-[10px]">—</span>;

  const w = 56, h = 18, pad = 1;
  const min = Math.min(...pts, ...(avg && avg > 0 ? [avg] : []));
  const max = Math.max(...pts, ...(avg && avg > 0 ? [avg] : []));
  const range = max - min || 1;
  const x = (i: number) => pad + (i / (pts.length - 1)) * (w - 2 * pad);
  const y = (v: number) => pad + (1 - (v - min) / range) * (h - 2 * pad);

  const last = pts[pts.length - 1];
  const prev = pts[pts.length - 2];
  const trending = last < prev ? (lower_is_better ? "down-good" : "down-bad") : last > prev ? (lower_is_better ? "up-bad" : "up-good") : "flat";
  const lineColor = trending === "down-good" || trending === "up-good" ? "#4ade80" : trending === "flat" ? "#94a3b8" : "#f87171";

  const polyline = pts.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const avgY = avg && avg > 0 ? y(avg) : null;

  return (
    <div className="flex items-center gap-1">
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="shrink-0">
        {avgY != null && (
          <line x1={0} y1={avgY} x2={w} y2={avgY} stroke="#94a3b8" strokeWidth={0.5} strokeDasharray="2,2" opacity={0.5} />
        )}
        <polyline points={polyline} fill="none" stroke={lineColor} strokeWidth={1.2} strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={x(pts.length - 1)} cy={y(last)} r={1.5} fill={lineColor} />
      </svg>
      <span className={`text-[10px] font-medium ${trending.includes("good") ? "text-green-400" : trending === "flat" ? "text-t-6" : "text-red-400"}`}>
        {trending.includes("down") ? "↘" : trending.includes("up") ? "↗" : "→"}
      </span>
    </div>
  );
}

function MetricCell({ value, avg, history, metricKey, lower_is_better = true }: {
  value: number | null; avg: number | null;
  history?: { year: string; pe: number | null; p_ocf: number | null; ev_ebitda: number | null; peg: number | null }[];
  metricKey: "pe" | "p_ocf" | "ev_ebitda" | "peg";
  lower_is_better?: boolean;
}) {
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
  const histValues = history?.map((h) => h[metricKey]) ?? [];
  return (
    <div className="text-right space-y-0.5">
      <span className={`tnum font-medium ${color}`}>{formatted}</span>
      {avg != null && <div className="text-[10px] text-t-6 tnum">moy: {avg > 100 ? avg.toFixed(0) : avg.toFixed(1)}</div>}
      {histValues.length >= 2 && (
        <div className="flex justify-end">
          <Sparkline values={histValues} avg={avg} lower_is_better={lower_is_better} />
        </div>
      )}
    </div>
  );
}

function PegCell({ peg, fwd_peg, history }: { peg: number | null; fwd_peg: number | null; history?: { year: string; peg: number | null }[] }) {
  const val = fwd_peg ?? peg;
  if (val == null || val < 0 || val > 50) return <span className="text-t-6">—</span>;
  const color = val < 1 ? "text-green-400" : val > 2 ? "text-red-400" : "text-t-3";
  const histValues = history?.map((h) => h.peg) ?? [];
  return (
    <div className="text-right space-y-0.5">
      <span className={`tnum font-medium ${color}`}>{val.toFixed(2)}</span>
      <div className="text-[10px] text-t-6">{val < 1 ? "< 1 🟢" : val > 2 ? "> 2 🔴" : "fair"}</div>
      {histValues.length >= 2 && (
        <div className="flex justify-end">
          <Sparkline values={histValues} lower_is_better={true} />
        </div>
      )}
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
      <td className="px-3 py-3"><MetricCell value={d.pe} avg={d.pe_5y_avg} history={d.history} metricKey="pe" /></td>
      <td className="px-3 py-3"><PegCell peg={d.peg} fwd_peg={d.fwd_peg} history={d.history} /></td>
      <td className="px-3 py-3"><MetricCell value={d.p_ocf} avg={d.p_ocf_5y_avg} history={d.history} metricKey="p_ocf" /></td>
      <td className="px-3 py-3"><MetricCell value={d.ev_ebitda} avg={d.ev_ebitda_5y_avg} history={d.history} metricKey="ev_ebitda" /></td>
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
        right={
          <div className="flex items-center gap-3">
            <span className="text-t-3 font-medium">{signals.length} titres</span>
            <Badge variant="gain">{buyCount} opportunités</Badge>
            <span className="text-label text-t-6">Màj {new Date(updated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
          </div>
        }
      />

      {/* Top Opportunities with sparklines */}
      {top_opportunities.length > 0 && (
        <Section title="🎯 Top opportunités">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {top_opportunities.map((d) => {
              const peHist = d.history?.map((h) => h.pe) ?? [];
              const pocfHist = d.history?.map((h) => h.p_ocf) ?? [];
              return (
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
                      {peHist.length >= 2 && <div className="flex justify-center mt-0.5"><Sparkline values={peHist} avg={d.pe_5y_avg} /></div>}
                    </div>
                    <div>
                      <div className="text-t-6 text-[10px]">PEG</div>
                      <div className="tnum text-green-400 font-medium">{(d.fwd_peg ?? d.peg)?.toFixed(1) ?? "—"}</div>
                    </div>
                    <div>
                      <div className="text-t-6 text-[10px]">P/OCF</div>
                      <div className="tnum text-green-400 font-medium">{d.p_ocf?.toFixed(0) ?? "—"}</div>
                      {pocfHist.length >= 2 && <div className="flex justify-center mt-0.5"><Sparkline values={pocfHist} avg={d.p_ocf_5y_avg} /></div>}
                    </div>
                  </div>
                  <div className="mt-3 space-y-1">
                    {d.signals.filter((s) => s.signal === "buy").map((s, i) => (
                      <div key={i} className="text-[11px] text-green-400">▲ {s.reason}</div>
                    ))}
                  </div>
                </div>
              );
            })}
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
        <p>📈 Mini-graphes = évolution sur 5 ans · Ligne pointillée = moyenne · ↘ vert = ratio en baisse (bon signe)</p>
        <p>🟢 Vert = ratio &lt; 80% de la moyenne → opportunité · 🔴 Rouge = ratio &gt; 130% → surévalué</p>
        <p>Source: Financial Modeling Prep · Données annuelles (TTM) · Pas une recommandation d&apos;investissement</p>
      </div>
    </div>
  );
}
