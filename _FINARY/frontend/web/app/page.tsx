"use client";

import { useState, useCallback } from "react";
import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { BreakdownDonut } from "@/components/dashboard/BreakdownDonut";
import { InstitutionBar } from "@/components/dashboard/InstitutionBar";
import { NetWorthChart } from "@/components/charts/NetWorthChart";
import { useNetWorth, useAccounts } from "@/lib/hooks/useApi";
import { Loading, ErrorState, DetailSheet } from "@/components/ds";
import { formatEUR } from "@/lib/utils";

type SheetKind = null | "actifs" | "passifs" | "investissements" | "liquidites" | { class: string } | { institution: string };

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  checking: "Compte courant",
  savings: "Épargne",
  pea: "PEA",
  cto: "CTO",
  av: "Assurance-vie",
  loan: "Prêt",
  crypto: "Crypto",
};

export default function HomePage() {
  const { data: networth, isLoading, error } = useNetWorth();
  const { data: accounts } = useAccounts();
  const [sheet, setSheet] = useState<SheetKind>(null);

  const close = useCallback(() => setSheet(null), []);

  if (isLoading) return <Loading />;
  if (error) return <ErrorState />;
  if (!networth) return null;

  // Filter accounts based on sheet type
  const getSheetTitle = (): string => {
    if (sheet === "actifs") return "Actifs";
    if (sheet === "passifs") return "Passifs";
    if (sheet === "investissements") return "Investissements";
    if (sheet === "liquidites") return "Liquidités";
    if (sheet && typeof sheet === "object" && "class" in sheet) return sheet.class;
    if (sheet && typeof sheet === "object" && "institution" in sheet) {
      const inst = networth.by_institution.find((i) => i.name === sheet.institution);
      return inst?.display_name ?? sheet.institution;
    }
    return "";
  };

  const getSheetAccounts = () => {
    if (!accounts) return [];
    if (sheet === "actifs") return accounts.filter((a) => a.balance > 0);
    if (sheet === "passifs") return accounts.filter((a) => a.balance < 0);
    if (sheet === "investissements") return accounts.filter((a) => ["pea", "cto", "av", "crypto"].includes(a.account_type));
    if (sheet === "liquidites") return accounts.filter((a) => ["checking", "savings"].includes(a.account_type));
    if (sheet && typeof sheet === "object" && "institution" in sheet) return accounts.filter((a) => a.institution === sheet.institution);
    if (sheet && typeof sheet === "object" && "class" in sheet) {
      const classMap: Record<string, string[]> = {
        Liquidites: ["checking"],
        Epargne: ["savings"],
        Investissements: ["pea", "cto", "av", "crypto"],
      };
      const types = classMap[sheet.class];
      if (types) return accounts.filter((a) => types.includes(a.account_type));
      return [];
    }
    return [];
  };

  const sheetAccounts = getSheetAccounts();
  const sheetTotal = sheetAccounts.reduce((s, a) => s + a.balance, 0);

  return (
    <div className="space-y-8">
      <NetWorthChart />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="cursor-pointer" onClick={() => setSheet("actifs")}>
          <NetWorthCard
            label="Actifs"
            value={networth.total_assets}
            variation={networth.variation_month}
          />
        </div>
        <div className="cursor-pointer" onClick={() => setSheet("passifs")}>
          <NetWorthCard label="Passifs" value={networth.total_liabilities} negative />
        </div>
        <div className="cursor-pointer" onClick={() => setSheet("investissements")}>
          <NetWorthCard label="Investissements" value={networth.breakdown.investments} />
        </div>
        <div className="cursor-pointer" onClick={() => setSheet("liquidites")}>
          <NetWorthCard
            label="Liquidités"
            value={networth.breakdown.cash + networth.breakdown.savings}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <BreakdownDonut
          breakdown={networth.breakdown}
          onSliceClick={(cls) => setSheet({ class: cls })}
        />
        <InstitutionBar
          institutions={networth.by_institution}
          onItemClick={(name) => setSheet({ institution: name })}
        />
      </div>

      {/* Detail sheet */}
      <DetailSheet
        open={!!sheet}
        onClose={close}
        title={getSheetTitle()}
        subtitle={`${sheetAccounts.length} compte${sheetAccounts.length > 1 ? "s" : ""} · ${formatEUR(sheetTotal)}`}
      >
        <div className="space-y-1">
          {sheetAccounts
            .sort((a, b) => Math.abs(b.balance) - Math.abs(a.balance))
            .map((acc) => (
              <div
                key={acc.id}
                className="flex items-center justify-between py-3 px-2 -mx-2 rounded-lg hover:bg-bg-hover transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-body text-t-2 truncate">{acc.name}</p>
                  <p className="text-label text-t-5 mt-0.5">
                    {acc.institution_display_name} · {ACCOUNT_TYPE_LABELS[acc.account_type] || acc.account_type}
                    {acc.is_pro && " · Pro"}
                  </p>
                </div>
                <span className={`tnum text-body font-medium ml-3 shrink-0 ${acc.balance < 0 ? "text-loss" : "text-t-1"}`}>
                  {formatEUR(acc.balance)}
                </span>
              </div>
            ))}
          {sheetAccounts.length === 0 && (
            <p className="text-body text-t-5 text-center py-8">Aucun compte</p>
          )}
        </div>
      </DetailSheet>
    </div>
  );
}
