"use client";

import { useLoans } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";
import { Loading, ErrorState, PageHeader, Badge, Section } from "@/components/ds";

export default function LoansPage() {
  const { data: loans, isLoading, error } = useLoans();

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
          <Section title="Endettement total">
            <p className="tnum text-heading font-semibold text-loss">{formatEUR(totalRemaining)}</p>
            <div className="bar-track mt-3" style={{ height: "6px" }}>
              <div className="bar-fill w-full bg-loss" />
            </div>
          </Section>
        </div>
      )}

      {/* Table */}
      <Section>
        <div className="-mx-7 -mb-7 overflow-hidden">
          <table className="w-full text-body">
          <thead>
            <tr className="border-b border-bd-1">
              {["Crédit", "Établissement", "Type", "Restant", "Mensualité", "Taux", "vs Inflation", "Conseil"].map((h, i) => (
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
                <td className="tnum text-right px-3 py-3 font-medium text-loss">{formatEUR(loan.remaining)}</td>
                <td className="tnum text-right px-3 py-3 text-t-2">
                  {loan.monthly_payment ? formatEUR(loan.monthly_payment) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 text-t-4">
                  {loan.rate_numeric != null ? `${loan.rate_numeric.toFixed(2)}%` : "—"}
                  {loan.real_rate != null && (
                    <span className={`block text-caption ${loan.real_rate <= 0 ? "text-gain" : "text-loss"}`}>
                      réel: {loan.real_rate > 0 ? "+" : ""}{loan.real_rate.toFixed(2)}%
                    </span>
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
                     loan.vs_inflation === "neutre" ? "≈ Neutre" : "❓ Inconnu"}
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
                      {loan.insurance_remaining_est != null && ` · Assurance est.: ${formatEUR(loan.insurance_remaining_est)}`}
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
