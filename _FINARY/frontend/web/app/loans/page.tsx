"use client";

import { useLoans, useLoansAnalysis } from "@/lib/hooks/useApi";
import { formatEUR, formatEURCompact } from "@/lib/utils";
import { Loading, ErrorState, PageHeader, Badge, Section, SourceBadge } from "@/components/ds";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function LoansPage() {
  const { data: loans, isLoading, error } = useLoans();
  const { data: analysis } = useLoansAnalysis();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;

  const totalRemaining = loans?.reduce((s: number, l: any) => s + (l.remaining ?? 0), 0) ?? 0;
  const totalMonthly = loans?.reduce((s: number, l: any) => s + (l.monthly_payment ?? 0), 0) ?? 0;
  const shields = loans?.filter((l: any) => l.vs_inflation === "bouclier_inflation") ?? [];
  const costly = loans?.filter((l: any) => l.vs_inflation === "rembourser") ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        label="Crédits & Emprunts"
        value={-totalRemaining}
        valueColor="text-loss"
        right={
          <div>
            <p className="text-label mb-1 text-t-5">Mensualités</p>
            <p className="tnum text-heading font-medium text-t-1">
              {formatEUR(totalMonthly)}<span className="text-label text-t-5">/mois</span>
            </p>
          </div>
        }
      />

      {/* Inflation summary */}
      {loans && loans.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Section title="Boucliers inflation">
            <p className="tnum text-heading font-semibold text-gain">{shields.length}</p>
            <p className="text-label text-t-5 mt-1">Taux &lt; inflation 2.4% — garder le plus longtemps</p>
          </Section>
          <Section title="Coûteux">
            <p className="tnum text-heading font-semibold text-loss">{costly.length}</p>
            <p className="text-label text-t-5 mt-1">Taux &gt; inflation — rembourser en priorité</p>
          </Section>
          <Section title="Gain inflation à 10 ans">
            <p className="tnum text-heading font-semibold text-gain">
              {(analysis as any)?.summary?.inflation_gain_10y ? formatEURCompact((analysis as any).summary.inflation_gain_10y) : "—"}
            </p>
            <p className="text-label text-t-5 mt-1">
              L&apos;inflation réduit la valeur réelle de votre dette
            </p>
          </Section>
        </div>
      )}

      {/* Inflation erosion chart */}
      {(analysis as any)?.projections && (
        <Section title="Dette nominale vs valeur réelle (inflation 2.4%/an)">
          <p className="text-label text-t-5 mb-4">
            En euros constants, votre dette perd de la valeur chaque année grâce à l&apos;inflation
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={(analysis as any).projections} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />
              <XAxis dataKey="year" tick={{ fontSize: 11, fill: "var(--text-5)" }} tickFormatter={(v: number) => `${v}a`} />
              <YAxis tick={{ fontSize: 11, fill: "var(--text-5)" }} tickFormatter={(v: number) => `${Math.round(v / 1000)}K`} />
              <Tooltip
                contentStyle={{ background: "var(--bg-3)", border: "1px solid var(--border-2)", borderRadius: 8, fontSize: 12 }}
                formatter={(v: any, name: any) => [formatEURCompact(v), name === "nominal_debt" ? "Nominal" : name === "real_debt" ? "Réel" : "Érosion"]}
                labelFormatter={(l: any) => `Année ${l}`}
              />
              <Area type="monotone" dataKey="nominal_debt" stroke="var(--red)" fill="var(--red-bg)" strokeWidth={2} name="Nominal" />
              <Area type="monotone" dataKey="real_debt" stroke="var(--green)" fill="var(--green-bg)" strokeWidth={2} name="Réel" />
            </AreaChart>
          </ResponsiveContainer>
        </Section>
      )}

      {/* Table */}
      <Section>
        <div className="-mx-7 -mb-7 overflow-hidden">
          <table className="w-full text-body">
          <thead>
            <tr className="border-b border-bd-1">
              {["Crédit", "Établissement", "Type", "Restant", "Mensualité", "Assurance", "Taux", "vs Inflation", "Conseil"].map((h, i) => (
                <th key={h} className={`${i === 0 ? "text-left pl-5" : "text-right"} px-3 py-3 text-caption font-medium uppercase text-t-6`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loans?.map((loan: any, i: number) => (
              <tr key={i} className="border-b border-bd-1 transition-colors cursor-default hover:bg-bg-hover">
                <td className="pl-5 px-3 py-3">
                  <p className="font-medium text-t-1">{loan.name}</p>
                  {loan.remaining_months && (
                    <p className="text-label mt-0.5 text-t-5">{loan.remaining_months} mois restants</p>
                  )}
                </td>
                <td className="text-right px-3 py-3 text-t-3">{loan.institution}</td>
                <td className="text-right px-3 py-3">
                  <Badge variant={loan.type === "PTZ" ? "gain" : loan.type === "margin" ? "warn" : "accent"}>
                    {loan.type?.toUpperCase()}
                  </Badge>
                </td>
                <td className="tnum text-right px-3 py-3 font-medium text-loss">
                  <div className="flex items-center justify-end gap-1.5">
                    {formatEUR(loan.remaining)}
                    <SourceBadge source={loan.institution === "Interactive Brokers" ? "live" : "scraped"} />
                  </div>
                </td>
                <td className="tnum text-right px-3 py-3 text-t-2">
                  {loan.monthly_payment ? formatEUR(loan.monthly_payment) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 text-t-4">
                  {loan.insurance_monthly > 0 ? `${formatEUR(loan.insurance_monthly)}/mo` :
                   loan.insurance_monthly === 0 ? <span className="text-t-5 text-caption">Aucune</span> :
                   <span className="text-t-6">—</span>}
                </td>
                <td className="tnum text-right px-3 py-3 text-t-2">
                  {loan.rate_numeric != null ? (
                    <div>
                      <div className="flex items-center justify-end gap-1">
                        <span className="font-medium">{loan.rate_numeric.toFixed(2)}%</span>
                        {loan.rate_type && <span className="text-caption text-t-5">{loan.rate_type}</span>}
                        <SourceBadge source={loan.institution === "Interactive Brokers" ? "live" : "scraped"} />
                      </div>
                      {loan.real_rate != null && (
                        <div className={`text-caption mt-0.5 ${loan.real_rate <= 0 ? "text-gain" : "text-loss"}`}>
                          réel {loan.real_rate > 0 ? "+" : ""}{loan.real_rate.toFixed(2)}%
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-t-6">—</span>
                  )}
                </td>
                <td className="text-right px-3 py-3">
                  <Badge variant={
                    loan.vs_inflation === "bouclier_inflation" ? "gain" :
                    loan.vs_inflation === "rembourser" ? "loss" :
                    loan.vs_inflation === "neutre" ? "neutral" : "warn"
                  }>
                    {loan.vs_inflation === "bouclier_inflation" ? "🛡️ Bouclier" :
                     loan.vs_inflation === "rembourser" ? "⚠️ Rembourser" :
                     loan.vs_inflation === "neutre" ? "≈ Neutre" : "🔍 Non scrapé"}
                  </Badge>
                </td>
                <td className="text-right px-3 pr-5 py-3 text-label text-t-4 max-w-[200px]">
                  {loan.recommendation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </Section>

      {/* Detailed recommendation cards */}
      {loans && loans.some((l: any) => l.recommendation_detail) && (
        <Section title="Analyse détaillée">
          <div className="space-y-3">
            {loans.filter((l: any) => l.recommendation_detail).map((loan: any, i: number) => (
              <div key={i} className="flex items-start gap-3 py-2">
                <Badge variant={loan.vs_inflation === "bouclier_inflation" ? "gain" : loan.vs_inflation === "rembourser" ? "loss" : "neutral"}>
                  {loan.vs_inflation === "bouclier_inflation" ? "🛡️" : loan.vs_inflation === "rembourser" ? "⚠️" : "—"}
                </Badge>
                <div>
                  <p className="text-body font-medium text-t-1">{loan.name} — {loan.institution}</p>
                  <p className="text-label text-t-4 mt-0.5">{loan.recommendation_detail}</p>
                  {loan.total_interest_remaining != null && (
                    <p className="text-caption text-t-5 mt-1">
                      Intérêts restants: {formatEUR(loan.total_interest_remaining)}
                      {loan.insurance_remaining_est != null && ` · Assurance: ${formatEUR(loan.insurance_remaining_est)}`}
                      {loan.total_cost_remaining != null && (
                        <span className="font-medium text-t-3"> · Coût total: {formatEUR(loan.total_cost_remaining)}</span>
                      )}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
