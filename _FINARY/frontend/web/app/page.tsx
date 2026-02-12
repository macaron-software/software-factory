"use client";

import { useState, useCallback } from "react";
import { NetWorthCard } from "@/components/dashboard/NetWorthCard";
import { BreakdownDonut } from "@/components/dashboard/BreakdownDonut";
import { InstitutionBar } from "@/components/dashboard/InstitutionBar";
import { NetWorthChart } from "@/components/charts/NetWorthChart";
import { useNetWorth, useAccounts, usePatrimoineProjection } from "@/lib/hooks/useApi";
import { Loading, ErrorState, DetailSheet, Section } from "@/components/ds";
import { formatEUR, formatEURCompact } from "@/lib/utils";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

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
  const { data: projection } = usePatrimoineProjection();
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
    const own = accounts.filter((a) => !a.excluded);
    if (sheet === "actifs") return own.filter((a) => a.balance > 0);
    if (sheet === "passifs") return own.filter((a) => a.balance < 0);
    if (sheet === "investissements") return own.filter((a) => ["pea", "cto", "av", "crypto"].includes(a.account_type));
    if (sheet === "liquidites") return own.filter((a) => ["checking", "savings"].includes(a.account_type));
    if (sheet && typeof sheet === "object" && "institution" in sheet) return own.filter((a) => a.institution === sheet.institution);
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

  const src = networth.sources;

  return (
    <div className="space-y-8">
      <NetWorthChart liveValue={networth.net_worth} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="cursor-pointer" onClick={() => setSheet("actifs")}>
          <NetWorthCard
            label="Actifs"
            value={networth.total_assets}
            variation={networth.variation_month}
            source="computed"
          />
        </div>
        <div className="cursor-pointer" onClick={() => setSheet("passifs")}>
          <NetWorthCard label="Passifs" value={networth.total_liabilities} negative source={src?.liabilities} />
        </div>
        <div className="cursor-pointer" onClick={() => setSheet("investissements")}>
          <NetWorthCard label="Investissements" value={networth.breakdown.investments} source={src?.investments} />
        </div>
        <div className="cursor-pointer" onClick={() => setSheet("liquidites")}>
          <NetWorthCard
            label="Liquidités"
            value={networth.breakdown.cash + networth.breakdown.savings}
            source={src?.cash}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <BreakdownDonut
          breakdown={networth.breakdown}
          onSliceClick={(cls) => setSheet({ class: cls })}
          sources={src}
        />
        <InstitutionBar
          institutions={networth.by_institution}
          onItemClick={(name) => setSheet({ institution: name })}
        />
      </div>

      {/* Patrimoine projection (inflation-adjusted) */}
      {(projection as any)?.projections && (
        <Section title="Projection patrimoniale (€ constants)">
          <div className="flex items-center gap-4 mb-4">
            <p className="text-label text-t-5">
              Inflation {(projection as any).inflation_rate}%/an · Actions {(projection as any).assumptions?.stock_return}%/an · Immobilier +{(projection as any).assumptions?.real_estate_extra}%/an réel
            </p>
            {(projection as any).projections?.[10] && (
              <span className="tnum text-caption font-medium px-2 py-0.5 rounded" style={{ background: "var(--green-bg)", color: "var(--green)" }}>
                10 ans: {formatEURCompact((projection as any).projections[10].net_real)}
              </span>
            )}
            {(projection as any).projections?.[20] && (
              <span className="tnum text-caption font-medium px-2 py-0.5 rounded" style={{ background: "var(--accent-bg)", color: "var(--accent)" }}>
                20 ans: {formatEURCompact((projection as any).projections[20].net_real)}
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={(projection as any).projections} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" />
              <XAxis dataKey="year" tick={{ fontSize: 11, fill: "var(--text-5)" }} tickFormatter={(v: number) => `${v}a`} />
              <YAxis tick={{ fontSize: 11, fill: "var(--text-5)" }} tickFormatter={(v: number) => `${Math.round(v / 1000)}K`} />
              <Tooltip
                contentStyle={{ background: "var(--bg-3)", border: "1px solid var(--border-2)", borderRadius: 8, fontSize: 12 }}
                formatter={(v: any, name: any) => {
                  const labels: Record<string, string> = { net_real: "Net réel", real_estate_real: "Immobilier", investments_real: "Investissements", debt_real: "Dette" };
                  return [formatEURCompact(v as number), labels[name] || name];
                }}
                labelFormatter={(l: any) => `Année ${l}`}
              />
              <Legend formatter={(value: string) => {
                const labels: Record<string, string> = { net_real: "Net réel", real_estate_real: "Immobilier", investments_real: "Investissements", debt_real: "Dette" };
                return labels[value] || value;
              }} />
              <Area type="monotone" dataKey="real_estate_real" stackId="assets" stroke="var(--accent)" fill="var(--accent-bg)" strokeWidth={1.5} />
              <Area type="monotone" dataKey="investments_real" stackId="assets" stroke="var(--green)" fill="var(--green-bg)" strokeWidth={1.5} />
              <Area type="monotone" dataKey="debt_real" stroke="var(--red)" fill="var(--red-bg)" strokeWidth={2} />
              <Area type="monotone" dataKey="net_real" stroke="var(--text-1)" fill="none" strokeWidth={2} strokeDasharray="5 3" />
            </AreaChart>
          </ResponsiveContainer>
        </Section>
      )}

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
