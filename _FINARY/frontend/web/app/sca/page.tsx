"use client";

import { useSCA, useSCALegal } from "@/lib/hooks/useApi";
import { formatEUR, formatEURCompact, CHART_COLORS } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import { Loading, ErrorState, PageHeader, Badge, Section, StatCard } from "@/components/ds";

type BadgeVariant = "gain" | "loss" | "accent" | "warn" | "neutral";

/** Format ISO date as "DD/MM/YYYY" */
function fmtDate(iso: string) {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

const STATUS_MAP: Record<string, { label: string; variant: BadgeVariant }> = {
  terminée: { label: "Terminée", variant: "neutral" },
  en_cours: { label: "En cours", variant: "warn" },
  en_attente: { label: "En attente", variant: "neutral" },
  en_preparation: { label: "En préparation", variant: "accent" },
};

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function SCAPage() {
  const { data: sca, isLoading: loadingSCA } = useSCA();
  const { data: legal, isLoading: loadingLegal, error } = useSCALegal();

  if (loadingSCA || loadingLegal) return <Loading />;
  if (error) return <ErrorState />;
  if (!sca || !legal) return null;

  const s = (legal as any).summary;
  const procedures = (legal as any).procedures as any[];
  const strategy = (legal as any).strategy;
  const legalEntries = (legal as any).legal_entries as any[];
  const personalLegal = (legal as any).personal_legal as any[];
  const chartMonthly = (legal as any).chart_monthly as any[];
  const beaussierDebt = (legal as any).beaussier_debt;
  const beaussierLegal = (legal as any).beaussier_legal_estimate;
  const axelUnpaid = (legal as any).axel_unpaid;
  const cashflow = (legal as any).sca_cashflow as any[];

  const fin = sca.financials;
  const prop = sca.property;

  // Pie data for cost breakdown — combine SCA + perso categories
  const allCats: Record<string, number> = {};
  const LABELS: Record<string, string> = {
    avocat: "Avocat (SCA)", huissier: "Huissier", condamnation: "Condamnation Art. L.761-1",
    publication: "Publication JO", expertise_judiciaire: "Expertise judiciaire",
    études_géomètre: "Géomètre (BET Seals)", études_architecte: "Architecte (permis modif.)",
    acquisition_notaire: "Notaire (acquisition terrain)", greffe: "Greffe (perso)",
  };
  if (s.by_category_sca) {
    for (const [k, v] of Object.entries(s.by_category_sca)) allCats[k] = (allCats[k] || 0) + (v as number);
  }
  if (s.by_category_perso) {
    for (const [k, v] of Object.entries(s.by_category_perso)) {
      const key = k === "avocat" ? "avocat_perso" : k;
      allCats[key] = (allCats[key] || 0) + (v as number);
    }
  }
  if (allCats["avocat_perso"]) LABELS["avocat_perso"] = "Avocat (perso)";
  const costPie = Object.entries(allCats)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([k, v]) => ({ name: LABELS[k] || k, value: v }));

  // Monthly cashflow for chart
  const cashflowByMonth: Record<string, { in: number; out: number }> = {};
  for (const c of cashflow) {
    const m = c.date.slice(0, 7);
    if (!cashflowByMonth[m]) cashflowByMonth[m] = { in: 0, out: 0 };
    if (c.amount > 0) cashflowByMonth[m].in += c.amount;
    else cashflowByMonth[m].out += c.amount;
  }
  const cashflowChart = Object.entries(cashflowByMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, v]) => ({
      month: month.slice(2), // YY-MM
      in: Math.round(v.in),
      out: Math.round(Math.abs(v.out)),
    }));

  return (
    <div className="space-y-8">
      <PageHeader
        label={`SCA La Désirade — ${prop.address}`}
        value={sca.your_share_property_value}
        suffix={`${prop.type}, ${prop.surface_m2}m²`}
      />

      {/* ─── KPI Cards ─── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Valeur estimée" value={sca.your_share_property_value} tone="accent" />
        <StatCard label="Coût construction" value={fin.total_verse} />
        <StatCard label="Frais procédure" value={s.total_legal_all} tone="negative" />
        <StatCard label="Impayés Beaussier" value={beaussierDebt.af_impayes} tone="negative" />
      </div>

      {/* ─── Estimation Beaussier + Axel Unpaid ─── */}
      <div className="grid md:grid-cols-2 gap-6">
        {beaussierLegal && (
          <Section title="💸 Estimation frais Beaussier (Me Vernhet)">
            <p className="text-t-4 text-xs mb-3 italic">{beaussierLegal.note}</p>
            <div className="space-y-1.5 mb-4">
              {beaussierLegal.procedures?.map((p: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-xs gap-2">
                  <div className="flex-1 min-w-0">
                    <span className="text-t-2 truncate block">{p.name}</span>
                    {p.note && <span className="text-t-5 text-[10px]">{p.note}</span>}
                  </div>
                  <span className="text-loss font-mono shrink-0">
                    {formatEUR(p.estimate_low)}–{formatEUR(p.estimate_high)}
                  </span>
                </div>
              ))}
            </div>
            <div className="border-t border-bd-1 pt-3 flex justify-between text-sm font-semibold">
              <span className="text-t-2">Total estimé Beaussier</span>
              <span className="text-loss font-mono">
                {formatEUR(beaussierLegal.total_low)}–{formatEUR(beaussierLegal.total_high)}
              </span>
            </div>
            {beaussierLegal.condamnation_hah_perdu && (
              <div className="mt-3 p-3 rounded-lg bg-loss/10 border border-loss/20">
                <p className="text-loss text-xs font-semibold mb-1">⚖️ Condamnation appel perdu (31/03)</p>
                <div className="flex justify-between text-xs">
                  <span className="text-t-3">Art. 700 CPC</span>
                  <span className="text-loss font-mono">
                    {formatEUR(beaussierLegal.condamnation_hah_perdu.art_700.low)}–{formatEUR(beaussierLegal.condamnation_hah_perdu.art_700.high)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-t-3">Dépens</span>
                  <span className="text-loss font-mono">
                    {formatEUR(beaussierLegal.condamnation_hah_perdu.depens.low)}–{formatEUR(beaussierLegal.condamnation_hah_perdu.depens.high)}
                  </span>
                </div>
              </div>
            )}
          </Section>
        )}

        {axelUnpaid && (
          <Section title="📋 Situation Me Saint Martin">
            <div className="space-y-3">
              <div>
                <p className="text-t-4 text-xs font-semibold mb-2">Factures SCA payées</p>
                <div className="space-y-1">
                  {axelUnpaid.paid_sca?.map((p: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs">
                      <span className="text-t-3">{fmtDate(p.date)} — {p.desc}</span>
                      <span className="text-t-1 font-mono">{formatEUR(p.amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-xs font-semibold mt-1 pt-1 border-t border-bd-1/30">
                  <span className="text-t-2">Total payé SCA</span>
                  <span className="text-t-1 font-mono">{formatEUR(axelUnpaid.total_paid_sca)}</span>
                </div>
              </div>

              <div>
                <p className="text-t-4 text-xs font-semibold mb-2">Paiements perso</p>
                <div className="space-y-1">
                  {axelUnpaid.paid_perso?.map((p: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs">
                      <span className="text-t-3">{fmtDate(p.date)} — {p.desc}</span>
                      <span className="text-t-1 font-mono">{formatEUR(p.amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-xs font-semibold mt-1 pt-1 border-t border-bd-1/30">
                  <span className="text-t-2">Total payé perso</span>
                  <span className="text-t-1 font-mono">{formatEUR(axelUnpaid.total_paid_perso)}</span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-bg-1 border border-bd-1 space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-accent">SCA doit à Legland</span>
                  <span className="text-accent font-mono font-semibold">{formatEUR(axelUnpaid.sca_owes_legland)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-loss">Beaussier QP impayée (SCA)</span>
                  <span className="text-loss font-mono font-semibold">{formatEUR(axelUnpaid.beaussier_qp_unpaid)}</span>
                </div>
                <p className="text-t-5 text-[10px] mt-1">{axelUnpaid.note}</p>
              </div>
            </div>
          </Section>
        )}
      </div>

      {/* ─── Strategy / Critical Path ─── */}
      {strategy && (
        <Section title="⚡ Chemin critique">
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <p className="text-loss text-xs font-semibold mb-2">
                ⏰ Dissolution SCA: {strategy.dissolution_date?.slice(0, 7)}
              </p>
              <p className="text-t-3 text-xs mb-3">{strategy.dissolution_note}</p>
              <p className="text-t-4 text-xs font-semibold mb-1">Stratégie adverse</p>
              <p className="text-t-3 text-xs mb-3">{strategy.adverse_strategy}</p>
              <p className="text-gain text-xs font-semibold mb-1">Notre contre-stratégie</p>
              <p className="text-t-2 text-xs">{strategy.our_counter}</p>
            </div>
            <div>
              <p className="text-t-4 text-xs font-semibold mb-2">Prochaines étapes clés</p>
              <div className="space-y-1.5">
                {strategy.critical_path?.map((step: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className="text-accent mt-0.5">›</span>
                    <span className="text-t-2">{step}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Section>
      )}

      {/* ─── Procedures Timeline ─── */}
      <Section title="Procédures en cours">
        <div className="space-y-4">
          {procedures.map((proc: any) => {
            const st = STATUS_MAP[proc.status] || STATUS_MAP.en_cours;
            const futureEvents = proc.key_dates.filter(
              (d: any) => d.date >= new Date().toISOString().slice(0, 10)
            );
            const pastEvents = proc.key_dates.filter(
              (d: any) => d.date < new Date().toISOString().slice(0, 10)
            );
            return (
              <div key={proc.id} className="card p-5 border border-bd-1">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h4 className="text-t-1 font-semibold text-sm">{proc.name}</h4>
                    <p className="text-t-4 text-xs mt-1">
                      {proc.lawyer} {proc.jurisdiction ? `— ${proc.jurisdiction}` : ""}
                    </p>
                    {proc.adverse && (
                      <p className="text-loss text-xs mt-0.5">vs {proc.adverse}</p>
                    )}
                  </div>
                  <Badge variant={st.variant}>{st.label}</Badge>
                </div>

                {proc.note && (
                  <p className="text-t-3 text-xs mb-3 italic border-l-2 border-accent pl-3">{proc.note}</p>
                )}

                {/* Future dates (highlighted) */}
                {futureEvents.length > 0 && (
                  <div className="mb-2">
                    {futureEvents.map((d: any, i: number) => (
                      <div key={i} className="flex items-start gap-3 py-1.5 text-xs">
                        <span className="text-accent font-mono font-semibold w-24 shrink-0">
                          {fmtDate(d.date)}
                        </span>
                        <span className="text-accent">{d.event}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Past dates (dimmed, collapsed if many) */}
                {pastEvents.length > 0 && (
                  <details className="text-xs">
                    <summary className="text-t-5 cursor-pointer mb-1">
                      {pastEvents.length} événement{pastEvents.length > 1 ? "s" : ""} passé{pastEvents.length > 1 ? "s" : ""}
                    </summary>
                    {pastEvents.map((d: any, i: number) => (
                      <div key={i} className="flex items-start gap-3 py-1 text-t-5">
                        <span className="font-mono w-24 shrink-0">{fmtDate(d.date)}</span>
                        <span>{d.event}</span>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      {/* ─── Legal Costs ─── */}
      <div className="grid md:grid-cols-2 gap-6">
        <Section title="Répartition frais juridiques">
          <div className="h-64">
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={costPie}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  label={({ name, value }: any) => `${name} ${formatEURCompact(value)}`}
                  labelLine={false}
                >
                  {costPie.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: any) => formatEUR(v)}
                  contentStyle={{ background: "var(--bg-2)", border: "1px solid var(--bd-1)", borderRadius: 8 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-4 text-xs">
            {costPie.map((c) => (
              <div key={c.name} className="flex justify-between">
                <span className="text-t-4">{c.name}</span>
                <span className="text-t-1">{formatEUR(c.value)}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Dépenses juridiques / mois">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={chartMonthly}>
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "var(--text-4)" }} tickFormatter={(v: string) => v.slice(2)} />
                <YAxis tick={{ fontSize: 10, fill: "var(--text-4)" }} tickFormatter={(v: any) => `${Math.round(v / 1000)}K`} />
                <Tooltip
                  formatter={(v: any) => formatEUR(v)}
                  contentStyle={{ background: "var(--bg-2)", border: "1px solid var(--bd-1)", borderRadius: 8 }}
                />
                <Bar dataKey="amount" fill="var(--red)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>

      {/* ─── SCA Cashflow ─── */}
      <Section title="Flux de trésorerie SCA">
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center">
            <p className="text-t-4 text-xs">Versé à SCA</p>
            <p className="text-loss text-lg font-semibold">{formatEUR(Math.abs(s.total_sca_cashflow_out))}</p>
          </div>
          <div className="text-center">
            <p className="text-t-4 text-xs">Remboursé par SCA</p>
            <p className="text-gain text-lg font-semibold">{formatEUR(s.total_sca_cashflow_in)}</p>
          </div>
          <div className="text-center">
            <p className="text-t-4 text-xs">Net</p>
            <p className="text-loss text-lg font-semibold">
              {formatEUR(Math.abs(s.total_sca_cashflow_out) - s.total_sca_cashflow_in)}
            </p>
          </div>
        </div>
        <div className="h-48">
          <ResponsiveContainer>
            <BarChart data={cashflowChart}>
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "var(--text-4)" }} />
              <YAxis tick={{ fontSize: 10, fill: "var(--text-4)" }} tickFormatter={(v: any) => `${Math.round(v / 1000)}K`} />
              <Tooltip
                formatter={(v: any, name: any) => [formatEUR(v), name === "out" ? "Versé" : "Reçu"]}
                contentStyle={{ background: "var(--bg-2)", border: "1px solid var(--bd-1)", borderRadius: 8 }}
              />
              <Bar dataKey="out" fill="var(--red)" radius={[4, 4, 0, 0]} name="Versé" />
              <Bar dataKey="in" fill="var(--green)" radius={[4, 4, 0, 0]} name="Reçu" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Section>

      {/* ─── Beaussier Situation ─── */}
      <Section title="Situation Beaussier">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <p className="text-t-4 text-xs">Parts</p>
            <p className="text-t-1 font-semibold">{sca.co_associate.ownership_pct.toFixed(1)}%</p>
            <p className="text-t-5 text-xs">{sca.co_associate.parts.toLocaleString("fr-FR")} parts</p>
          </div>
          <div>
            <p className="text-t-4 text-xs">AF Impayés</p>
            <p className="text-loss font-semibold">{formatEUR(beaussierDebt.af_impayes)}</p>
          </div>
          <div>
            <p className="text-t-4 text-xs">Capital non libéré</p>
            <p className="text-loss font-semibold">{formatEUR(beaussierDebt.capital_non_libere)}</p>
          </div>
          <div>
            <p className="text-t-4 text-xs">Fournisseurs QP</p>
            <p className="text-loss font-semibold">{formatEUR(beaussierDebt.fournisseurs_qp)}</p>
          </div>
        </div>
      </Section>

      {/* ─── Detail Tables ─── */}
      <div className="grid md:grid-cols-2 gap-6">
        <Section title="Factures juridiques SCA">
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-t-4 border-b border-bd-1">
                  <th className="text-left py-2">Date</th>
                  <th className="text-left py-2">Type</th>
                  <th className="text-left py-2">Description</th>
                  <th className="text-right py-2">Montant</th>
                </tr>
              </thead>
              <tbody>
                {legalEntries.map((e: any, i: number) => (
                  <tr key={i} className="border-b border-bd-1/30">
                    <td className="py-1.5 font-mono text-t-4">{fmtDate(e.date)}</td>
                    <td className="py-1.5">
                      <Badge variant={e.category === "avocat" ? "warn" : e.category === "huissier" ? "accent" : "neutral"}>
                        {e.category}
                      </Badge>
                    </td>
                    <td className="py-1.5 text-t-2 max-w-[200px] truncate">{e.description}</td>
                    <td className="py-1.5 text-right text-loss font-mono">{formatEUR(e.amount)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-bd-1 font-semibold">
                  <td colSpan={3} className="py-2 text-t-2">Total SCA</td>
                  <td className="py-2 text-right text-loss font-mono">{formatEUR(s.total_legal_sca)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Section>

        <Section title="Paiements perso (hors SCA)">
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-t-4 border-b border-bd-1">
                  <th className="text-left py-2">Date</th>
                  <th className="text-left py-2">Description</th>
                  <th className="text-right py-2">Montant</th>
                </tr>
              </thead>
              <tbody>
                {personalLegal.map((e: any, i: number) => (
                  <tr key={i} className="border-b border-bd-1/30">
                    <td className="py-1.5 font-mono text-t-4">{fmtDate(e.date)}</td>
                    <td className="py-1.5 text-t-2">{e.description}</td>
                    <td className="py-1.5 text-right text-loss font-mono">{formatEUR(e.amount)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-bd-1 font-semibold">
                  <td colSpan={2} className="py-2 text-t-2">Total perso</td>
                  <td className="py-2 text-right text-loss font-mono">{formatEUR(s.total_legal_personal)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Section>
      </div>

      {/* ─── Financials Summary ─── */}
      <Section title="Situation financière SCA">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-t-4 text-xs mb-1">Capital souscrit</p>
            <p className="text-t-1 font-semibold">{formatEUR(fin.capital_souscrit)}</p>
          </div>
          <div>
            <p className="text-t-4 text-xs mb-1">Capital versé</p>
            <p className="text-t-1 font-semibold">{formatEUR(fin.capital_verse)}</p>
          </div>
          <div>
            <p className="text-t-4 text-xs mb-1">CCA (avances)</p>
            <p className="text-t-1 font-semibold">{formatEUR(fin.cca_avances)}</p>
          </div>
          <div>
            <p className="text-t-4 text-xs mb-1">Total versé</p>
            <p className="text-accent font-semibold">{formatEUR(fin.total_verse)}</p>
          </div>
          <div>
            <p className="text-t-4 text-xs mb-1">Solde bancaire</p>
            <p className="text-t-1 font-semibold">{formatEUR(fin.bank_account_balance)}</p>
          </div>
          <div>
            <p className="text-t-4 text-xs mb-1">AF impayés (vous)</p>
            <p className="text-loss font-semibold">{formatEUR(fin.af_impayes)}</p>
          </div>
        </div>
      </Section>
    </div>
  );
}
