"use client";

import { useState, useMemo, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { PeriodSelector, periodToDays, type Period } from "./PeriodSelector";
import { formatEUR, formatPct } from "@/lib/utils";
import { useNetWorthHistory } from "@/lib/hooks/useApi";
import { SourceBadge } from "@/components/ds";

interface ChartPoint {
  date: string;
  label: string;
  value: number;
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr);
  const months = ["Jan", "Fev", "Mar", "Avr", "Mai", "Jun", "Jul", "Aou", "Sep", "Oct", "Nov", "Dec"];
  return `${d.getDate()} ${months[d.getMonth()]}`;
}

function formatMonthLabel(dateStr: string): string {
  const d = new Date(dateStr);
  const months = ["Jan", "Fev", "Mar", "Avr", "Mai", "Jun", "Jul", "Aou", "Sep", "Oct", "Nov", "Dec"];
  return `${months[d.getMonth()]} ${d.getFullYear().toString().slice(2)}`;
}

export function NetWorthChart() {
  const [period, setPeriod] = useState<Period>("1Y");
  const [hoverValue, setHoverValue] = useState<number | null>(null);
  const { data: apiHistory } = useNetWorthHistory(365);

  const rawHistory = useMemo(() => {
    if (apiHistory && apiHistory.length > 0) return apiHistory;
    return [];
  }, [apiHistory]);

  const chartData = useMemo<ChartPoint[]>(() => {
    const days = periodToDays(period);
    const sliced = rawHistory.slice(-days);
    return sliced.map((d) => ({
      date: d.date,
      label: formatDateLabel(d.date),
      value: d.net_worth,
    }));
  }, [rawHistory, period]);

  // Compute variation
  const currentValue = chartData[chartData.length - 1]?.value ?? 0;
  const startValue = chartData[0]?.value ?? 0;
  const variation = startValue > 0 ? ((currentValue - startValue) / startValue) * 100 : 0;
  const variationAbs = currentValue - startValue;
  const isPositive = variation >= 0;

  const displayValue = hoverValue ?? currentValue;

  // X-axis ticks
  const tickInterval = useMemo(() => {
    if (chartData.length <= 30) return Math.ceil(chartData.length / 6);
    if (chartData.length <= 90) return Math.ceil(chartData.length / 8);
    return Math.ceil(chartData.length / 10);
  }, [chartData.length]);

  const formatXTick = useCallback(
    (dateStr: string) => {
      if (chartData.length > 90) return formatMonthLabel(dateStr);
      return formatDateLabel(dateStr);
    },
    [chartData.length]
  );

  // Y domain with padding
  const [yMin, yMax] = useMemo(() => {
    const values = chartData.map((d) => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1 || 1000;
    return [Math.floor((min - padding) / 1000) * 1000, Math.ceil((max + padding) / 1000) * 1000];
  }, [chartData]);

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-2" style={{ color: "var(--text-5)" }}>
            Patrimoine net <SourceBadge source="computed" />
          </p>
          <p className="tnum text-[32px] font-extralight tracking-tight leading-none" style={{ color: "var(--text-1)" }}>
            {formatEUR(displayValue)}
          </p>
          <div className="flex items-center gap-2 mt-2">
            <span
              className="tnum text-[13px] font-medium"
              style={{ color: isPositive ? "var(--green)" : "var(--red)" }}
            >
              {isPositive ? "+" : ""}{formatEUR(variationAbs)}
            </span>
            <span
              className="tnum text-[11px] font-medium px-2 py-0.5 rounded"
              style={{
                background: isPositive ? "var(--green-bg)" : "var(--red-bg)",
                color: isPositive ? "var(--green)" : "var(--red)",
              }}
            >
              {formatPct(variation)}
            </span>
          </div>
        </div>
        <PeriodSelector selected={period} onChange={setPeriod} />
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart
          data={chartData}
          margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
          onMouseMove={(e) => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const payload = (e as any)?.activePayload;
            if (payload?.[0]) {
              setHoverValue(payload[0].payload.value);
            }
          }}
          onMouseLeave={() => setHoverValue(null)}
        >
          <XAxis
            dataKey="date"
            interval={tickInterval}
            tickFormatter={formatXTick}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: "var(--text-6)" }}
            dy={8}
          />
          <YAxis
            domain={[yMin, yMax]}
            tickFormatter={(v: number) => `€${v.toLocaleString("fr-FR")}`}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: "var(--text-6)" }}
            width={72}
          />
          <Tooltip
            content={() => null}
            cursor={{
              stroke: "var(--text-5)",
              strokeWidth: 1,
              strokeDasharray: "4 4",
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#5682f2"
            strokeWidth={1.5}
            fill="none"
            dot={false}
            activeDot={{
              r: 4,
              fill: "#5682f2",
              stroke: "var(--bg-3)",
              strokeWidth: 2,
            }}
            animationDuration={800}
            animationEasing="ease-out"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
