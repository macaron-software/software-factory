"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { formatEUR, CHART_COLORS } from "@/lib/utils";

interface Props {
  institutions: { name: string; display_name: string; total: number }[];
}

export function InstitutionBar({ institutions }: Props) {
  const data = institutions
    .filter((i) => i.total !== 0)
    .sort((a, b) => b.total - a.total);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <h3 className="text-sm font-medium text-gray-500 mb-4">
        Par établissement
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} layout="vertical">
          <XAxis type="number" tickFormatter={(v) => formatEUR(v)} />
          <YAxis
            type="category"
            dataKey="display_name"
            width={150}
            tick={{ fontSize: 12 }}
          />
          <Tooltip formatter={(v: number) => formatEUR(v)} />
          <Bar dataKey="total" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
