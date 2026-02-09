"use client";

import { useLoans } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";

export default function LoansPage() {
  const { data: loans, isLoading, error } = useLoans();

  if (isLoading)
    return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;
  if (error)
    return <div className="text-[13px]" style={{ color: "var(--red)" }}>Erreur de connexion API</div>;

  const totalRemaining = loans?.reduce((s, l) => s + l.remaining, 0) ?? 0;
  const totalMonthly = loans?.reduce((s, l) => s + (l.monthly_payment ?? 0), 0) ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-2" style={{ color: "var(--text-5)" }}>
            Crédits & Emprunts
          </p>
          <p className="tnum text-[32px] font-extralight tracking-tight leading-none" style={{ color: "var(--red)" }}>
            {formatEUR(-totalRemaining)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[11px] mb-1" style={{ color: "var(--text-5)" }}>Mensualités</p>
          <p className="tnum text-[18px] font-medium" style={{ color: "var(--text-1)" }}>
            {formatEUR(totalMonthly)}<span className="text-[11px]" style={{ color: "var(--text-5)" }}>/mois</span>
          </p>
        </div>
      </div>

      {/* Progress bar total */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[12px] font-medium" style={{ color: "var(--text-3)" }}>Endettement total</span>
          <span className="tnum text-[13px] font-medium" style={{ color: "var(--red)" }}>{formatEUR(totalRemaining)}</span>
        </div>
        <div className="bar-track" style={{ height: "8px" }}>
          <div className="bar-fill" style={{ width: "100%", background: "var(--red)" }} />
        </div>
      </div>

      {/* Loans list */}
      <div className="card overflow-hidden">
        <table className="w-full text-[13px]">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-1)" }}>
              {["Crédit", "Établissement", "Type", "Emprunté", "Restant", "Mensualité", "Taux"].map((h, i) => (
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
            {loans?.map((loan, i) => {
              const paidPct = loan.borrowed ? ((loan.borrowed - loan.remaining) / loan.borrowed * 100) : 0;
              return (
                <tr
                  key={i}
                  className="transition-colors cursor-default"
                  style={{ borderBottom: "1px solid var(--border-1)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <td className="pl-5 px-3 py-3">
                    <div>
                      <p className="font-medium" style={{ color: "var(--text-1)" }}>{loan.name}</p>
                      {loan.status && (
                        <p className="text-[11px] mt-0.5" style={{ color: "var(--text-5)" }}>{loan.status}</p>
                      )}
                    </div>
                  </td>
                  <td className="text-right px-3 py-3" style={{ color: "var(--text-3)" }}>{loan.institution}</td>
                  <td className="text-right px-3 py-3">
                    <span
                      className="text-[10px] font-medium px-2 py-0.5 rounded"
                      style={{
                        background: loan.type === "PTZ" ? "var(--green-bg)" : loan.type === "margin" ? "var(--orange-bg)" : "var(--accent-bg)",
                        color: loan.type === "PTZ" ? "var(--green)" : loan.type === "margin" ? "var(--orange)" : "var(--accent)",
                      }}
                    >
                      {loan.type?.toUpperCase()}
                    </span>
                  </td>
                  <td className="tnum text-right px-3 py-3" style={{ color: "var(--text-5)" }}>
                    {loan.borrowed ? formatEUR(loan.borrowed) : "—"}
                  </td>
                  <td className="tnum text-right px-3 py-3 font-medium" style={{ color: "var(--red)" }}>
                    {formatEUR(loan.remaining)}
                  </td>
                  <td className="tnum text-right px-3 py-3" style={{ color: "var(--text-2)" }}>
                    {loan.monthly_payment ? formatEUR(loan.monthly_payment) : "—"}
                  </td>
                  <td className="tnum text-right px-3 pr-5 py-3" style={{ color: "var(--text-4)" }}>
                    {loan.rate ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
