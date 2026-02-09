"use client";

import { useAccounts } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";
import { Loading, ErrorState, PageHeader } from "@/components/ds";

const TYPE_LABELS: Record<string, string> = {
  checking: "Compte courant",
  savings: "Épargne",
  pea: "PEA",
  cto: "CTO",
  av: "Assurance Vie",
  loan: "Crédit",
};

export default function AccountsPage() {
  const { data: accounts, isLoading, error } = useAccounts();

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;

  const totalBalance = accounts?.reduce((s, a) => s + a.balance, 0) ?? 0;

  const grouped = (accounts ?? []).reduce<Record<string, typeof accounts>>((acc, a) => {
    const key = a.institution_display_name || a.institution;
    if (!acc[key]) acc[key] = [];
    acc[key]!.push(a);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <PageHeader label="Solde total" value={totalBalance} />

      <div className="space-y-5">
        {Object.entries(grouped).map(([institution, accs]) => {
          const instTotal = accs!.reduce((s, a) => s + a.balance, 0);
          return (
            <div key={institution}>
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-label font-medium tracking-[0.02em] uppercase text-t-5">
                  {institution}
                </span>
                <span className="tnum text-label font-medium text-t-4">{formatEUR(instTotal)}</span>
              </div>
              <div className="card overflow-hidden divide-y divide-bd-1">
                {accs!.map((acc) => (
                  <div
                    key={acc.id}
                    className="flex items-center justify-between px-5 py-3.5 transition-colors cursor-default hover:bg-bg-hover"
                  >
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="text-body font-medium text-t-1">{acc.name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-label text-t-5">
                            {TYPE_LABELS[acc.account_type] || acc.account_type}
                          </span>
                          {acc.is_pro && (
                            <span className="bg-accent-bg text-accent text-caption font-medium px-1.5 py-px rounded">
                              Pro
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <p className={`tnum text-body-lg font-medium ${acc.balance < 0 ? "text-loss" : "text-t-1"}`}>
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
