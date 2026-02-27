"use client";

import { useSCA, useSCALegal, useDVFGrabels } from "@/lib/hooks/useApi";
import { formatEUR, formatEURCompact, CHART_COLORS } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import { Loading, ErrorState, PageHeader, Badge, Section, StatCard } from "@/components/ds";
import {
  DollarSign, Scale, Ban, FileText, Wrench, XCircle, Clock,
  Gavel, Zap, Timer, ClipboardList, CheckCircle, AlertCircle,
  TrendingUp, Home, Key, ShieldCheck,
} from "lucide-react";

/** Render event text, replacing [TAG] prefixes with Lucide icons */
function renderEvent(text: string) {
  const tagMap: Record<string, { icon: React.ReactNode; cls: string }> = {
    "[DELIBERE]": { icon: <Gavel className="w-3 h-3 inline mr-1" />, cls: "text-accent font-semibold" },
    "[AUDIENCE]": { icon: <Scale className="w-3 h-3 inline mr-1" />, cls: "text-accent font-semibold" },
    "[DEADLINE]": { icon: <ClipboardList className="w-3 h-3 inline mr-1" />, cls: "" },
    "[RISQUE]": { icon: <AlertCircle className="w-3 h-3 inline mr-1" />, cls: "text-loss" },
    "[A PLANIFIER]": { icon: <Clock className="w-3 h-3 inline mr-1" />, cls: "text-t-3" },
  };
  for (const [tag, { icon, cls }] of Object.entries(tagMap)) {
    if (text.startsWith(tag)) {
      return <span className={cls}>{icon}{text.slice(tag.length + 1)}</span>;
    }
  }
  return text;
}

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
  const { data: dvf } = useDVFGrabels();

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
  const cashflow = (legal as any).sca_cashflow as any[];
  const scenario = (legal as any).scenario_rachat;

  const fin = sca.financials;
  const prop = sca.property;

  // Pie data for cost breakdown — combine SCA + perso categories
  const allCats: Record<string, number> = {};
  const LABELS: Record<string, string> = {
    avocat: "Avocat (SCA)", huissier: "Huissier", condamnation: "Condamnation Art. L.761-1",
    publication: "Publication JO", expertise_judiciaire: "Expertise judiciaire",
    études_géomètre: "Géomètre (BET Seals)", études_architecte: "Architecte (permis modif.)",
    greffe: "Greffe (perso)",
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

      {/* ─── PTZ Alert ─── */}
      {(legal as any).ptz_alert && (() => {
        const ptz = (legal as any).ptz_alert;
        return (
          <Section title={<span className="flex items-center gap-2"><AlertCircle className="w-4 h-4 text-loss" />Alerte PTZ — {ptz.dossier}</span>}>
            <div className="bg-loss/10 border border-loss/30 rounded-lg p-4 space-y-3">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-t-1 font-semibold">Relance Crédit Agricole du {fmtDate(ptz.lettre_date)}</p>
                  <p className="text-t-3 text-xs">{ptz.emetteur} — Agence {ptz.agence}</p>
                </div>
                <Badge variant="loss">{formatEUR(ptz.restant_a_debloquer)} à débloquer</Badge>
              </div>
              <p className="text-loss text-sm font-medium">{ptz.risque}</p>
              <div>
                <p className="text-t-2 text-xs font-semibold mb-1">Justificatifs demandés :</p>
                <ul className="text-t-3 text-xs space-y-1 list-disc pl-4">
                  {ptz.justificatifs_demandes.map((j: string, i: number) => <li key={i}>{j}</li>)}
                </ul>
              </div>
              <p className="text-t-4 text-xs italic">Alternative : {ptz.alternative_si_pas_habitable}</p>
              <div className="border-t border-bd-1 pt-3 mt-2">
                <p className="text-t-2 text-xs font-semibold mb-1 flex items-center gap-1"><CheckCircle className="w-3 h-3 text-gain" />Réponse envoyée le {fmtDate(ptz.reponse_envoyee.date)}</p>
                <p className="text-t-3 text-xs mb-2">{ptz.reponse_envoyee.objet}</p>
                <ul className="text-t-4 text-xs space-y-1">
                  {ptz.reponse_envoyee.pieces_jointes.map((p: any, i: number) => (
                    <li key={i} className="flex items-start gap-1">
                      <FileText className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{p.nom}{p.note && <span className="text-loss ml-1">({p.note})</span>}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <p className="text-loss/70 text-xs mt-2 italic">🔒 {ptz.blocage_actuel}</p>
            </div>
          </Section>
        );
      })()}
      {scenario && (
        <Section title={<span className="flex items-center gap-2"><Key className="w-4 h-4 text-accent" />Scénario : {scenario.titre}</span>}>
          <p className="text-t-3 text-xs mb-4 italic border-l-2 border-accent pl-3">{scenario.hypothese}</p>

          {/* KPI scenario */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="p-3 rounded-lg bg-gain/5 border border-gain/20 text-center">
              <p className="text-t-4 text-[10px] mb-1">Prix d&apos;adjudication</p>
              <p className="text-gain text-xl font-bold">1 €</p>
              <p className="text-t-5 text-[10px]">Seul enchérisseur</p>
            </div>
            <div className="p-3 rounded-lg bg-bg-1 border border-bd-1 text-center">
              <p className="text-t-4 text-[10px] mb-1">Surface acquise</p>
              <p className="text-t-1 text-xl font-bold">{scenario.acquisition.surface_acquise_m2} m²</p>
              <p className="text-t-5 text-[10px]">{scenario.acquisition.resultat}</p>
            </div>
            <div className="p-3 rounded-lg bg-bg-1 border border-bd-1 text-center">
              <p className="text-t-4 text-[10px] mb-1">Valeur lot fini (ancien)</p>
              <p className="text-accent text-xl font-bold">{formatEURCompact(scenario.valeur_acquise.lot_beaussier_fini_ancien)}</p>
              <p className="text-t-5 text-[10px]">Neuf: {formatEURCompact(scenario.valeur_acquise.lot_beaussier_fini_neuf)}</p>
            </div>
            <div className="p-3 rounded-lg bg-gain/5 border border-gain/20 text-center">
              <p className="text-t-4 text-[10px] mb-1">Gain net estimé</p>
              <p className="text-gain text-xl font-bold">{formatEURCompact(scenario.gain_net.mid)}</p>
              <p className="text-t-5 text-[10px]">{formatEURCompact(scenario.gain_net.low)}–{formatEURCompact(scenario.gain_net.high)}</p>
            </div>
          </div>

          {/* Base légale + Procédure */}
          {scenario.base_legale && (
            <div className="space-y-6 mb-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div className="p-3 rounded-lg bg-bg-1 border border-bd-1">
                  <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Gavel className="w-3.5 h-3.5 text-accent" />Base légale</p>
                  <p className="text-accent text-xs font-mono mb-2">{scenario.base_legale.article}</p>
                  {scenario.base_legale.texte_cle && (
                    <blockquote className="text-t-3 text-xs italic border-l-2 border-accent/40 pl-2 mb-3">{scenario.base_legale.texte_cle}</blockquote>
                  )}
                  <p className="text-t-3 text-xs mb-3">{scenario.base_legale.mecanisme}</p>
                  <p className="text-t-4 text-[10px] font-semibold mb-1">Conditions remplies :</p>
                  <div className="space-y-1">
                    {scenario.base_legale.conditions.map((c: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <CheckCircle className="w-3 h-3 text-gain mt-0.5 shrink-0" />
                        <span className="text-t-2">{c}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-bg-1 border border-bd-1">
                  <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><ClipboardList className="w-3.5 h-3.5" />Procédure ({scenario.base_legale.delai_estime})</p>
                  <div className="space-y-1.5">
                    {scenario.base_legale.procedure.map((step: string, i: number) => {
                      const done = step.includes("✅");
                      const label = step.replace(/^\d+\.\s*/, "").replace(/\s*✅\s*/g, " ").replace(/\(FAIT[^)]*\)/g, "").trim();
                      return (
                        <div key={i} className={`flex items-start gap-2 text-xs ${done ? "opacity-60" : ""}`}>
                          {done
                            ? <CheckCircle className="w-3.5 h-3.5 text-gain mt-0.5 shrink-0" />
                            : <span className="text-accent font-mono font-bold w-4 shrink-0 text-right">{i + 1}</span>
                          }
                          <span className={done ? "text-t-4 line-through" : "text-t-2"}>{label}</span>
                          {done && <span className="text-gain text-[10px] font-semibold">FAIT</span>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
              {/* Avantages vs procédure judiciaire */}
              {scenario.base_legale.avantages_vs_judiciaire && (
                <div className="p-3 rounded-lg bg-gain/5 border border-gain/20">
                  <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5 text-gain" />Avantages vs procédure judiciaire</p>
                  <div className="grid md:grid-cols-2 gap-x-6 gap-y-1">
                    {scenario.base_legale.avantages_vs_judiciaire.map((a: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <CheckCircle className="w-3 h-3 text-gain mt-0.5 shrink-0" />
                        <span className="text-t-3">{a}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Pourquoi aucun repreneur */}
          {scenario.pourquoi_aucun_repreneur && (
            <div className="p-3 rounded-lg bg-loss/5 border border-loss/20 mb-6">
              <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Ban className="w-3.5 h-3.5 text-loss" />Pourquoi aucun repreneur aux enchères</p>
              <div className="grid md:grid-cols-2 gap-x-6 gap-y-1">
                {scenario.pourquoi_aucun_repreneur.map((r: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <XCircle className="w-3 h-3 text-loss mt-0.5 shrink-0" />
                    <span className="text-t-3">{r}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stratégie dissolution — filet de sécurité */}
          {scenario.strategie_dissolution && (
            <div className="p-3 rounded-lg bg-accent/5 border border-accent/20 mb-6">
              <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5 text-accent" />{scenario.strategie_dissolution.titre}</p>
              <p className="text-t-3 text-xs mb-3">{scenario.strategie_dissolution.logique}</p>
              <div className="space-y-2">
                {scenario.strategie_dissolution.scenarios.map((s: any, i: number) => (
                  <div key={i} className="p-2 rounded bg-bg-1 border border-bd-1">
                    <p className="text-accent text-[10px] font-semibold">{s.cas}</p>
                    <p className="text-t-3 text-xs">{s.resultat}</p>
                    <p className="text-gain text-[10px] font-semibold">→ {s.issue}</p>
                  </div>
                ))}
              </div>
              <p className="text-gain text-xs font-semibold mt-2 text-center">{scenario.strategie_dissolution.conclusion}</p>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            {/* Coûts (finition + frais vente forcée) */}
            <div className="space-y-4">
              {/* Frais vente forcée */}
              {scenario.frais_vente_forcee && (
                <div>
                  <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Gavel className="w-3.5 h-3.5" />Frais vente forcée</p>
                  <div className="space-y-1">
                    {[
                      { label: "Huissier (mise en demeure)", value: scenario.frais_vente_forcee.huissier_mise_en_demeure },
                      { label: "PV Assemblée Générale", value: scenario.frais_vente_forcee.pv_ag },
                      { label: "Publication JAL", value: scenario.frais_vente_forcee.publication_jal },
                      { label: "LRAR notification", value: scenario.frais_vente_forcee.lrar_notification },
                      { label: "Cahier des charges + adjudication", value: scenario.frais_vente_forcee.cahier_charges_adjudication },
                      { label: "Avocat (accompagnement)", value: scenario.frais_vente_forcee.avocat_accompagnement },
                    ].map((c) => (
                      <div key={c.label} className="flex justify-between text-xs">
                        <span className="text-t-3">{c.label}</span>
                        <span className="text-loss font-mono">{formatEUR(c.value)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between text-xs font-semibold mt-2 pt-2 border-t border-bd-1">
                    <span className="text-t-2">Total frais vente forcée</span>
                    <span className="text-loss font-mono">{formatEUR(scenario.frais_vente_forcee.total)}</span>
                  </div>
                  <p className="text-t-5 text-[10px] mt-1 italic">{scenario.frais_vente_forcee.note}</p>
                </div>
              )}

              {/* Coûts finition */}
              <div>
                <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Wrench className="w-3.5 h-3.5" />Coûts de finition</p>
                <p className="text-t-5 text-[10px] mb-1">{scenario.couts_finition.note}</p>
                <div className="space-y-1">
                  {[
                    { label: "Économique", value: scenario.couts_finition.economique },
                    { label: "Standard", value: scenario.couts_finition.standard },
                    { label: "Qualité", value: scenario.couts_finition.qualite },
                  ].map((c) => (
                    <div key={c.label} className="flex justify-between text-xs">
                      <span className="text-t-3">{c.label}</span>
                      <span className="text-loss font-mono">{formatEUR(c.value)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Patrimoine avant/après */}
              <div>
                <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Home className="w-3.5 h-3.5" />Patrimoine immobilier</p>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-t-4">Avant (lot Legland seul)</span>
                    <span className="text-t-2 font-mono">{formatEUR(scenario.patrimoine.avant)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-t-3">Après (207m² fini, ancien)</span>
                    <span className="text-accent font-mono font-semibold">{formatEUR(scenario.patrimoine.apres_low)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-t-3">Après (207m² fini, neuf)</span>
                    <span className="text-accent font-mono font-semibold">{formatEUR(scenario.patrimoine.apres_high)}</span>
                  </div>
                </div>
                <div className="flex justify-between text-xs font-semibold mt-2 pt-2 border-t border-gain/30">
                  <span className="text-gain flex items-center gap-1"><TrendingUp className="w-3 h-3" />Plus-value nette</span>
                  <span className="text-gain font-mono">{formatEUR(scenario.patrimoine.plus_value_low)}–{formatEUR(scenario.patrimoine.plus_value_high)}</span>
                </div>
              </div>
            </div>

            {/* Dettes annulées + option locative + leviers */}
            <div className="space-y-4">
              <div>
                <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Ban className="w-3.5 h-3.5 text-gain" />Dettes Beaussier éteintes</p>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-t-3">AF impayés</span>
                    <span className="text-gain font-mono">{formatEUR(scenario.dettes_annulees.af_impayes)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-t-3">Fournisseurs QP</span>
                    <span className="text-gain font-mono">{formatEUR(scenario.dettes_annulees.fournisseurs_qp)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-t-3">QP procédures impayées</span>
                    <span className="text-gain font-mono">{formatEUR(scenario.dettes_annulees.qp_procedures)}</span>
                  </div>
                </div>
                <div className="flex justify-between text-xs font-semibold mt-2 pt-2 border-t border-gain/30">
                  <span className="text-gain">Total dettes éteintes</span>
                  <span className="text-gain font-mono">{formatEUR(scenario.dettes_annulees.total)}</span>
                </div>
                <p className="text-t-5 text-[10px] mt-1">+ capital non libéré: {formatEUR(scenario.dettes_annulees.capital_non_libere)} (théorique)</p>
              </div>

              {/* Option locative */}
              <div className="p-3 rounded-lg bg-accent/5 border border-accent/20">
                <p className="text-t-2 text-xs font-semibold mb-2">💰 Option locative (lot fini)</p>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-t-3">{scenario.option_locative.note}</span>
                    <span className="text-accent font-mono font-semibold">{formatEUR(scenario.option_locative.loyer_mensuel)}/mois</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-t-4">Revenus annuels bruts</span>
                    <span className="text-accent font-mono">{formatEUR(scenario.option_locative.loyer_annuel)}/an</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-t-4">Rendement brut / coût finition</span>
                    <span className="text-accent font-mono">{scenario.option_locative.rendement_brut_pct}%</span>
                  </div>
                </div>
              </div>

              <div>
                <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5 text-accent" />Leviers de pression</p>
                <div className="space-y-1.5">
                  {scenario.leviers_pression.map((l: string, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="text-accent mt-0.5 shrink-0">›</span>
                      <span className="text-t-2">{l}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </Section>
      )}

      {/* ─── DVF Transactions Grabels ─── */}
      {dvf && !dvf.error && (
        <Section title={<span className="flex items-center gap-2"><Home className="w-4 h-4 text-accent" />Transactions immobilières Grabels (DVF)</span>}>
          <p className="text-t-4 text-xs mb-3">Source : {(dvf as any).source} — {(dvf as any).periode} — {(dvf as any).total} transactions</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="bg-bg-1 rounded-lg p-3 text-center">
              <p className="text-t-4 text-xs">Maisons médian</p>
              <p className="text-t-1 text-lg font-bold">{(dvf as any).stats?.maisons?.prix_m2_median?.toLocaleString()}€/m²</p>
              <p className="text-t-4 text-xs">{(dvf as any).stats?.maisons?.count} ventes</p>
            </div>
            <div className="bg-bg-1 rounded-lg p-3 text-center">
              <p className="text-t-4 text-xs">Apparts médian</p>
              <p className="text-t-1 text-lg font-bold">{(dvf as any).stats?.appartements?.prix_m2_median?.toLocaleString()}€/m²</p>
              <p className="text-t-4 text-xs">{(dvf as any).stats?.appartements?.count} ventes</p>
            </div>
            <div className="bg-bg-1 rounded-lg p-3 text-center border border-accent/30">
              <p className="text-t-4 text-xs">Comparable SCA (118m²)</p>
              <p className="text-accent text-lg font-bold">{(dvf as any).stats?.comparables_sca?.prix_m2_median?.toLocaleString()}€/m²</p>
              <p className="text-t-4 text-xs">{(dvf as any).stats?.comparables_sca?.count} ventes</p>
            </div>
            <div className="bg-bg-1 rounded-lg p-3 text-center border border-accent/30">
              <p className="text-t-4 text-xs">Estimation SCA DVF</p>
              <p className="text-accent text-lg font-bold">{formatEURCompact((dvf as any).stats?.comparables_sca?.estimation_sca_median)}</p>
              <p className="text-t-4 text-xs">médiane × 118m²</p>
            </div>
          </div>

          {/* Prix/m² chart by quarter */}
          {(dvf as any).chart_prix_m2?.length > 0 && (
            <div className="h-48 mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={(dvf as any).chart_prix_m2}>
                  <XAxis dataKey="quarter" tick={{ fill: "var(--text-4)", fontSize: 10 }} />
                  <YAxis tick={{ fill: "var(--text-4)", fontSize: 10 }} domain={[2000, "auto"]} />
                  <Tooltip contentStyle={{ background: "var(--bg-2)", border: "1px solid var(--border-1)", borderRadius: 8, fontSize: 12 }}
                    formatter={(v: number | undefined) => [`${(v ?? 0).toLocaleString()}€/m²`, "Prix médian"]} />
                  <Bar dataKey="prix_m2" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Rue des Cinsaults */}
          {(dvf as any).rue_des_cinsaults?.length > 0 && (
            <div>
              <p className="text-t-2 text-xs font-semibold mb-2">📍 Rue des Cinsaults (même rue que SCA)</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-t-4 border-b border-bd-1">
                    <th className="text-left py-1 pr-3">Date</th><th className="text-left pr-3">Type</th>
                    <th className="text-right pr-3">Prix</th><th className="text-right pr-3">Surface</th>
                    <th className="text-right">€/m²</th>
                  </tr></thead>
                  <tbody>
                    {(dvf as any).rue_des_cinsaults.map((t: any, i: number) => (
                      <tr key={i} className="border-b border-bd-1/50">
                        <td className="py-1 pr-3 text-t-3">{fmtDate(t.date)}</td>
                        <td className="pr-3 text-t-2">{t.type}</td>
                        <td className="text-right pr-3 text-t-1 font-medium">{formatEUR(t.prix)}</td>
                        <td className="text-right pr-3 text-t-3">{t.surface}m²</td>
                        <td className="text-right text-accent font-medium">{t.prix_m2.toLocaleString()}€</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Section>
      )}

      {/* ─── Estimation Beaussier + Axel Unpaid ─── */}
      <div className="grid md:grid-cols-2 gap-6">
        {beaussierLegal && (
          <Section title={<span className="flex items-center gap-2"><DollarSign className="w-4 h-4 text-loss" />Estimation frais Beaussier (Me Vernhet)</span>}>
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
                <p className="text-loss text-xs font-semibold mb-1 flex items-center gap-1.5"><Scale className="w-3.5 h-3.5" />Condamnation Art. 700 CPC (référé HAH 1ère instance)</p>
                <div className="flex justify-between text-xs">
                  <span className="text-t-3">Art. 700 → Legland (perso)</span>
                  <span className="text-loss font-mono">{formatEUR(beaussierLegal.condamnation_hah_perdu.art_700_legland)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-t-3">Art. 700 → SCA</span>
                  <span className="text-loss font-mono">{formatEUR(beaussierLegal.condamnation_hah_perdu.art_700_sca)}</span>
                </div>
                <div className="flex justify-between text-xs font-semibold mt-1 pt-1 border-t border-loss/30">
                  <span className="text-loss">Total condamnation</span>
                  <span className="text-loss font-mono">{formatEUR(beaussierLegal.condamnation_hah_perdu.total)}</span>
                </div>
              </div>
            )}
            {beaussierLegal.qp_impayes_sca && (
              <div className="mt-3 p-3 rounded-lg bg-loss/10 border border-loss/20">
                <p className="text-loss text-xs font-semibold mb-2 flex items-center gap-1.5"><Ban className="w-3.5 h-3.5" />QP Beaussier impayées (procédures SCA)</p>
                <div className="space-y-1">
                  {beaussierLegal.qp_impayes_sca.map((item: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs gap-2">
                      <span className="text-t-3 flex-1 min-w-0 truncate">{item.desc}</span>
                      <span className="text-loss font-mono shrink-0">{formatEUR(item.amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-xs font-semibold mt-2 pt-2 border-t border-loss/30">
                  <span className="text-loss">Total QP impayées</span>
                  <span className="text-loss font-mono">{formatEUR(beaussierLegal.total_qp_impayes)}</span>
                </div>
              </div>
            )}
            {beaussierLegal.prejudices && (() => {
              const pj = beaussierLegal.prejudices;
              return (
              <>
                {/* Préjudices Legland retenus par l'expert */}
                <div className="mt-4 p-3 rounded-lg border border-bd-1 bg-bg-1">
                  <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" />Préjudices Legland (rapport expert — 77 535€)</p>
                  <div className="space-y-1.5">
                    {pj.demandes_legland?.map((p: any, i: number) => (
                      <div key={i} className="text-xs">
                        <div className="flex justify-between gap-2">
                          <span className="text-t-3 flex-1 min-w-0 truncate">{p.desc}</span>
                          <div className="flex gap-3 shrink-0 font-mono">
                            <span className="text-t-4">{formatEUR(p.amount_demande)}</span>
                            <span className={p.amount_expert > 0 ? "text-gain" : "text-loss"}>{formatEUR(p.amount_expert)}</span>
                          </div>
                        </div>
                        {p.note && <span className="text-t-5 text-[10px]">{p.note}</span>}
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between text-xs font-semibold mt-2 pt-2 border-t border-bd-1">
                    <span className="text-t-4">Demandé / Retenu expert</span>
                    <div className="flex gap-3 font-mono">
                      <span className="text-t-4">{formatEUR(pj.total_demande_legland)}</span>
                      <span className="text-gain">{formatEUR(pj.total_expert_legland)}</span>
                    </div>
                  </div>
                </div>
                {/* Travaux remise en conformité — 100% Beaussier */}
                <div className="mt-3 p-3 rounded-lg border border-loss/20 bg-loss/5">
                  <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Wrench className="w-3.5 h-3.5" />Travaux remise en conformité (100% Beaussier)</p>
                  <div className="space-y-1">
                    {pj.travaux_remise_conformite?.map((p: any, i: number) => (
                      <div key={i} className="text-xs">
                        <div className="flex justify-between gap-2">
                          <span className="text-t-3 flex-1 min-w-0 truncate">{p.desc}</span>
                          <span className="text-loss font-mono shrink-0">{formatEUR(p.amount)}</span>
                        </div>
                        {p.note && <span className="text-t-5 text-[10px]">{p.note}</span>}
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between text-xs font-semibold mt-2 pt-2 border-t border-loss/30">
                    <span className="text-loss">Total travaux</span>
                    <span className="text-loss font-mono">{formatEUR(pj.total_travaux)}</span>
                  </div>
                  <p className="text-t-5 text-[10px] mt-1">{pj.note_travaux}</p>
                </div>
                {/* Demandes Beaussier — toutes rejetées par expert */}
                <div className="mt-3 p-3 rounded-lg border border-gain/20 bg-gain/5">
                  <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><XCircle className="w-3.5 h-3.5 text-gain" />Demandes Beaussier (expert : 0€)</p>
                  <div className="space-y-1">
                    {pj.demandes_beaussier?.map((p: any, i: number) => (
                      <div key={i} className="text-xs">
                        <div className="flex justify-between gap-2">
                          <span className="text-t-4 flex-1 min-w-0 truncate line-through">{p.desc}</span>
                          <div className="flex gap-3 shrink-0 font-mono">
                            <span className="text-t-5">{p.amount_demande ? formatEUR(p.amount_demande) : "—"}</span>
                            <span className="text-gain">0€</span>
                          </div>
                        </div>
                        {p.note && <span className="text-t-5 text-[10px]">{p.note}</span>}
                      </div>
                    ))}
                  </div>
                  <p className="text-gain text-[10px] mt-2 font-semibold">{pj.note_beaussier}</p>
                </div>
                {/* Demandes en cours */}
                {pj.demandes_en_cours && (
                  <div className="mt-3 p-3 rounded-lg border border-accent/20 bg-accent/5">
                    <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-accent" />Demandes en cours (pas encore jugées)</p>
                    <div className="space-y-2">
                      {pj.demandes_en_cours.map((d: any, i: number) => (
                        <div key={i} className="text-xs">
                          <div className="flex justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <span className="text-t-2 font-medium">{d.procedure}</span>
                              <span className="text-t-4 ml-2">({d.demandeur})</span>
                            </div>
                            <span className="text-accent font-mono shrink-0">
                              {formatEUR(d.estimation_low)}–{formatEUR(d.estimation_high)}
                            </span>
                          </div>
                          <p className="text-t-4">{d.desc}</p>
                          {d.note && <p className="text-t-5 text-[10px]">{d.note}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Condamnations prononcées */}
                {pj.condamnations && (
                  <div className="mt-3 p-3 rounded-lg border border-gain/30 bg-gain/5">
                    <p className="text-t-2 text-xs font-semibold mb-2 flex items-center gap-1.5"><Gavel className="w-3.5 h-3.5 text-gain" />Condamnations prononcées</p>
                    <div className="space-y-1">
                      {pj.condamnations.map((c: any, i: number) => (
                        <div key={i} className="flex justify-between text-xs gap-2">
                          <span className="text-t-3 flex-1">{c.desc}</span>
                          <span className="text-gain font-mono shrink-0">{c.amount ? formatEUR(c.amount) : "—"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
              );
            })()}
          </Section>
        )}

        {legal.axel_factures && (() => {
          const factures = legal.axel_factures as any[];
          const tot = legal.axel_totaux as any;
          return (
          <Section title={<span className="flex items-center gap-2"><ClipboardList className="w-4 h-4" />Factures Me Saint Martin</span>}>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-t-5 text-left border-b border-bd-1/30">
                  <th className="pb-1.5 font-medium">Date</th>
                  <th className="pb-1.5 font-medium">Description</th>
                  <th className="pb-1.5 font-medium">Ref</th>
                  <th className="pb-1.5 font-medium text-right">Montant</th>
                  <th className="pb-1.5 font-medium text-center">Tag</th>
                  <th className="pb-1.5 font-medium text-center">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-bd-1/20">
                {factures.map((f: any, i: number) => (
                  <tr key={i} className="hover:bg-bg-1/50">
                    <td className="py-1.5 text-t-4 whitespace-nowrap">{fmtDate(f.date)}</td>
                    <td className="py-1.5 text-t-2">{f.desc}</td>
                    <td className="py-1.5 text-t-5 font-mono">{f.ref !== "—" ? f.ref : ""}</td>
                    <td className="py-1.5 text-t-1 font-mono text-right">{f.amount != null ? formatEUR(f.amount) : <span className="text-t-5 italic">inconnu</span>}</td>
                    <td className="py-1.5 text-center">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        f.tag === "SCA" ? "bg-accent/15 text-accent" : "bg-blue-500/15 text-blue-400"
                      }`}>{f.tag}</span>
                    </td>
                    <td className="py-1.5 text-center">
                      {f.status === "payee" ? (
                        <span className="inline-flex items-center gap-1 text-gain text-[10px]">
                          <CheckCircle className="w-3 h-3" /> Payée
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-loss text-[10px]">
                          <AlertCircle className="w-3 h-3" /> Impayée
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-bd-1">
                <tr className="text-t-2 font-semibold">
                  <td colSpan={3} className="pt-2">Total connu</td>
                  <td className="pt-2 text-t-1 font-mono text-right">{formatEUR(tot.total_connu)}</td>
                  <td></td>
                  <td></td>
                </tr>
                <tr className="text-gain">
                  <td colSpan={3} className="pt-0.5">Payé</td>
                  <td className="pt-0.5 font-mono text-right">{formatEUR(tot.paye)}</td>
                  <td></td>
                  <td></td>
                </tr>
                {tot.impaye_connu > 0 && (
                  <tr className="text-loss font-semibold">
                    <td colSpan={3} className="pt-0.5">Impayé</td>
                    <td className="pt-0.5 font-mono text-right">{formatEUR(tot.impaye_connu)}</td>
                    <td></td>
                    <td></td>
                  </tr>
                )}
                {tot.note && (
                  <tr><td colSpan={6} className="pt-1 text-t-5 text-[10px] italic">{tot.note}</td></tr>
                )}
              </tfoot>
            </table>
          </Section>
          );
        })()}
      </div>

      {/* ─── Strategy / Critical Path ─── */}
      {strategy && (
        <Section title={<span className="flex items-center gap-2"><Zap className="w-4 h-4 text-accent" />Chemin critique</span>}>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <p className="text-loss text-xs font-semibold mb-2 flex items-center gap-1.5">
                <Timer className="w-3.5 h-3.5" />Dissolution SCA: {strategy.dissolution_date?.slice(0, 7)}
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
                    <h4 className="text-t-1 font-semibold text-sm">
                      {proc.name}
                      {proc.reference && <span className="text-t-4 font-normal ml-2">({proc.reference})</span>}
                    </h4>
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

                {/* Indemnités demandées (TA) */}
                {proc.indemnites_demandees && (
                  <details className="mb-3">
                    <summary className="text-gain text-xs font-semibold cursor-pointer flex items-center gap-1.5">
                      <Scale className="w-3.5 h-3.5" />
                      Indemnités demandées : {formatEURCompact(proc.indemnites_demandees.total_low)}–{formatEURCompact(proc.indemnites_demandees.total_high)}
                    </summary>
                    <div className="mt-2 space-y-1.5 pl-1">
                      {proc.indemnites_demandees.postes.map((p: any, j: number) => (
                        <div key={j} className="p-2 rounded bg-bg-1 border border-bd-1">
                          <div className="flex justify-between items-start">
                            <div>
                              <span className="text-t-2 text-xs font-semibold">{p.poste}</span>
                              <p className="text-t-4 text-[10px]">{p.description}</p>
                            </div>
                            <span className="text-gain text-xs font-mono whitespace-nowrap">{formatEURCompact(p.estimate_low)}–{formatEURCompact(p.estimate_high)}</span>
                          </div>
                          <p className="text-t-5 text-[10px] italic mt-0.5">{p.calcul}</p>
                        </div>
                      ))}
                      <div className="flex justify-between text-xs font-semibold pt-2 border-t border-bd-1">
                        <span className="text-t-2">Total indemnités demandées</span>
                        <span className="text-gain font-mono">{formatEURCompact(proc.indemnites_demandees.total_low)}–{formatEURCompact(proc.indemnites_demandees.total_high)}</span>
                      </div>
                      <p className="text-t-5 text-[10px] italic">{proc.indemnites_demandees.note}</p>
                    </div>
                  </details>
                )}

                {/* Future dates (highlighted) */}
                {futureEvents.length > 0 && (
                  <div className="mb-2">
                    {futureEvents.map((d: any, i: number) => (
                      <div key={i} className="flex items-start gap-3 py-1.5 text-xs">
                        <span className="text-accent font-mono font-semibold w-24 shrink-0">
                          {fmtDate(d.date)}
                        </span>
                        <span className="text-accent">{renderEvent(d.event)}</span>
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
                        <span>{renderEvent(d.event)}</span>
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
