"use client";

import { useAccounts } from "@/lib/hooks/useApi";
import { formatEUR } from "@/lib/utils";

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

  if (isLoading) return <div className="text-gray-500">Chargement...</div>;
  if (error) return <div className="text-red-500">Erreur: {error.message}</div>;

  const totalBalance = accounts?.reduce((s, a) => s + a.balance, 0) ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Comptes</h2>
        <p className="text-xl font-bold">{formatEUR(totalBalance)}</p>
      </div>

      <div className="space-y-3">
        {accounts?.map((acc) => (
          <div
            key={acc.id}
            className="bg-white rounded-lg border border-gray-200 p-4 hover:border-emerald-300 transition"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{acc.name}</p>
                <p className="text-xs text-gray-500">
                  {TYPE_LABELS[acc.account_type] || acc.account_type}
                  {acc.is_pro && (
                    <span className="ml-2 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                      PRO
                    </span>
                  )}
                </p>
              </div>
              <p
                className={`text-lg font-bold ${acc.balance < 0 ? "text-red-600" : "text-gray-900"}`}
              >
                {formatEUR(acc.balance)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
