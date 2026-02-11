"use client";

import { useMemo } from "react";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { formatEUR, formatEURCompact, formatPct } from "@/lib/utils";

interface Props {
  title: string;
  data: { date: string; value: number }[];
  color?: string;
  liveValue?: number;
  /** Show as index (percentage change from start) instead of absolute value */
  asIndex?: boolean;
}

export function MiniChart({ title, data, color = "#5682f2", liveValue, asIndex }: Props) {
  const chartData = useMemo(() => {
    if (!data.length) return [];
    if (asIndex) {
      const base = data[0].value;
      return data.map((d) => ({ ...d, value: base > 0 ? ((d.value - base) / base) * 100 : 0 }));
    }
    return data;
  }, [data, asIndex]);

  const current = liveValue ?? data[data.length - 1]?.value ?? 0;
  const start = data[0]?.value ?? 0;
  const changePct = start > 0 ? ((current - start) / start) * 100 : 0;
  const isPositive = changePct >= 0;

  const [yMin, yMax] = useMemo(() => {
    if (!chartData.length) return [0, 1];
    const vals = chartData.map((d) => d.value);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const pad = (max - min) * 0.15 || 1;
    return [min - pad, max + pad];
  }, [chartData]);

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-2">
        <p className="section-title">{title}</p>
        <span
          className="tnum text-[11px] font-medium px-1.5 py-0.5 rounded"
          style={{
            background: isPositive ? "var(--green-bg)" : "var(--red-bg)",
            color: isPositive ? "var(--green)" : "var(--red)",
          }}
        >
          {formatPct(changePct)}
        </span>
      </div>
      <p className="num-stat mb-3" style={{ color: "var(--text-1)" }}>
        {asIndex ? formatPct(changePct) : formatEURCompact(current)}
      </p>
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <YAxis domain={[yMin, yMax]} hide />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            animationDuration={400}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
