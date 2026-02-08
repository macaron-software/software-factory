"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { formatEUR } from "@/lib/utils";
import type { MonthlyBudget } from "@/lib/types/api";

interface Props {
  data: MonthlyBudget[];
}

function formatMonth(month: string): string {
  const d = new Date(month + "-01");
  const months = ["Jan", "Fev", "Mar", "Avr", "Mai", "Jun", "Jul", "Aou", "Sep", "Oct", "Nov", "Dec"];
  return months[d.getMonth()];
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const income = payload.find((p) => p.dataKey === "income")?.value ?? 0;
  const expenses = payload.find((p) => p.dataKey === "expenses")?.value ?? 0;
  const savings = income - expenses;
  return (
    <div
      style={{
        background: "var(--bg-3)",
        border: "1px solid var(--border-2)",
        borderRadius: 8,
        padding: "12px 16px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
        minWidth: 180,
      }}
    >
      <p className="text-[11px] mb-2" style={{ color: "var(--text-5)" }}>
        {label}
      </p>
      <div className="space-y-1.5">
        <div className="flex justify-between gap-6">
          <span className="text-[12px]" style={{ color: "var(--green)" }}>Revenus</span>
          <span className="tnum text-[12px] font-medium" style={{ color: "var(--text-1)" }}>
            {formatEUR(income)}
          </span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-[12px]" style={{ color: "var(--red)" }}>Depenses</span>
          <span className="tnum text-[12px] font-medium" style={{ color: "var(--text-1)" }}>
            {formatEUR(expenses)}
          </span>
        </div>
        <div
          className="flex justify-between gap-6 pt-1.5 mt-1"
          style={{ borderTop: "1px solid var(--border-1)" }}
        >
          <span className="text-[12px]" style={{ color: "var(--text-3)" }}>Epargne</span>
          <span
            className="tnum text-[12px] font-semibold"
            style={{ color: savings >= 0 ? "var(--green)" : "var(--red)" }}
          >
            {formatEUR(savings)}
          </span>
        </div>
      </div>
    </div>
  );
}

export function BudgetChart({ data }: Props) {
  const chartData = data.map((d) => ({
    ...d,
    label: formatMonth(d.month),
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chartData} barGap={2} barCategoryGap="20%">
        <CartesianGrid
          vertical={false}
          stroke="var(--border-1)"
          strokeDasharray="4 4"
          strokeOpacity={0.5}
        />
        <XAxis
          dataKey="label"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 10, fill: "var(--text-6)" }}
          dy={8}
        />
        <YAxis
          tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 10, fill: "var(--text-6)" }}
          width={40}
        />
        <Tooltip
          content={<CustomTooltip />}
          cursor={{ fill: "var(--bg-hover)", radius: 4 }}
        />
        <Bar
          dataKey="income"
          name="Revenus"
          fill="var(--green)"
          opacity={0.75}
          radius={[4, 4, 0, 0]}
          animationDuration={600}
        />
        <Bar
          dataKey="expenses"
          name="Depenses"
          fill="var(--red)"
          opacity={0.45}
          radius={[4, 4, 0, 0]}
          animationDuration={600}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
