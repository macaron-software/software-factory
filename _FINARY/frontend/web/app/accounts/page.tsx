"use client";

import { useAccounts } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";

const TYPE_LABELS: Record<string, string> = {
  checking: "Compte courant",
  savings: "Epargne",
  pea: "PEA",
  cto: "CTO",
  av: "Assurance Vie",
  loan: "Credit",
};

export default function AccountsPage() {
  const { data: accounts, isLoading, error } = useAccounts();

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

  const totalBalance = accounts?.reduce((s, a) => s + a.balance, 0) ?? 0;

  /* Group accounts by institution */
  const grouped = (accounts ?? []).reduce<Record<string, typeof accounts>>((acc, a) => {
    const key = a.institution_display_name || a.institution;
    if (!acc[key]) acc[key] = [];
    acc[key]!.push(a);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-[13px] font-medium mb-1" style={{ color: "var(--text-5)" }}>
          Solde total
        </p>
        <p className="tnum text-[32px] font-extralight tracking-tight leading-tight" style={{ color: "var(--text-1)" }}>
          {formatEUR(totalBalance)}
        </p>
      </div>

      {/* Grouped by institution */}
      <div className="space-y-4">
        {Object.entries(grouped).map(([institution, accs]) => {
          const instTotal = accs!.reduce((s, a) => s + a.balance, 0);
          return (
            <div key={institution}>
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-[12px] font-medium tracking-[0.02em] uppercase" style={{ color: "var(--text-5)" }}>
                  {institution}
                </span>
                <span className="tnum text-[12px] font-medium" style={{ color: "var(--text-4)" }}>
                  {formatEUR(instTotal)}
                </span>
              </div>
              <div className="card overflow-hidden divide-y" style={{ borderColor: "var(--border-1)" }}>
                {accs!.map((acc) => (
                  <div
                    key={acc.id}
                    className="flex items-center justify-between px-5 py-3.5 transition-colors cursor-default"
                    style={{ borderColor: "var(--border-1)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="text-[13px] font-medium" style={{ color: "var(--text-1)" }}>
                          {acc.name}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[11px]" style={{ color: "var(--text-5)" }}>
                            {TYPE_LABELS[acc.account_type] || acc.account_type}
                          </span>
                          {acc.is_pro && (
                            <span className="tag-accent text-[10px] font-medium px-1.5 py-px rounded">
                              Pro
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <p
                      className="tnum text-[14px] font-medium"
                      style={{ color: acc.balance < 0 ? "var(--red)" : "var(--text-1)" }}
                    >
                      {formatEUR(acc.balance)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
