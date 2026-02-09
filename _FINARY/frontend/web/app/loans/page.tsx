"use client";

import { useLoans } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";
import { Loading, ErrorState, PageHeader, Badge } from "@/components/ds";

export default function LoansPage() {
  const { data: loans, isLoading, error } = useLoans();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;

  const totalRemaining = loans?.reduce((s, l) => s + l.remaining, 0) ?? 0;
  const totalMonthly = loans?.reduce((s, l) => s + (l.monthly_payment ?? 0), 0) ?? 0;

  return (
    <div className="space-y-6">
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

      {/* Progress bar */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-body font-medium text-t-3">Endettement total</span>
          <span className="tnum text-body font-medium text-loss">{formatEUR(totalRemaining)}</span>
        </div>
        <div className="bar-track" style={{ height: "8px" }}>
          <div className="bar-fill w-full bg-loss" />
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full text-body">
          <thead>
            <tr className="border-b border-bd-1">
              {["Crédit", "Établissement", "Type", "Emprunté", "Restant", "Mensualité", "Taux"].map((h, i) => (
                <th key={h} className={`${i === 0 ? "text-left pl-5" : "text-right"} px-3 py-3 text-caption font-medium uppercase text-t-6`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loans?.map((loan, i) => (
              <tr key={i} className="border-b border-bd-1 transition-colors cursor-default hover:bg-bg-hover">
                <td className="pl-5 px-3 py-3">
                  <p className="font-medium text-t-1">{loan.name}</p>
                  {loan.status && <p className="text-label mt-0.5 text-t-5">{loan.status}</p>}
                </td>
                <td className="text-right px-3 py-3 text-t-3">{loan.institution}</td>
                <td className="text-right px-3 py-3">
                  <Badge variant={loan.type === "PTZ" ? "gain" : loan.type === "margin" ? "warn" : "accent"}>
                    {loan.type?.toUpperCase()}
                  </Badge>
                </td>
                <td className="tnum text-right px-3 py-3 text-t-5">
                  {loan.borrowed ? formatEUR(loan.borrowed) : "—"}
                </td>
                <td className="tnum text-right px-3 py-3 font-medium text-loss">{formatEUR(loan.remaining)}</td>
                <td className="tnum text-right px-3 py-3 text-t-2">
                  {loan.monthly_payment ? formatEUR(loan.monthly_payment) : "—"}
                </td>
                <td className="tnum text-right px-3 pr-5 py-3 text-t-4">{loan.rate ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
