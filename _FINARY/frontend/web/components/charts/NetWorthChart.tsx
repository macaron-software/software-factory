"use client";

import { useState, useMemo, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { PeriodSelector, periodToDays, type Period } from "./PeriodSelector";
import { formatEUR, formatPct } from "@/lib/utils";
import { useNetWorthHistory } from "@/lib/hooks/useApi";
import { generateNetWorthHistory } from "@/lib/fixtures";

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

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartPoint }> }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div
      className="chart-tooltip"
      style={{
        background: "var(--bg-3)",
        border: "1px solid var(--border-2)",
        borderRadius: 8,
        padding: "10px 14px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      }}
    >
      <p className="text-[11px] mb-1" style={{ color: "var(--text-5)" }}>
        {point.label}
      </p>
      <p className="tnum text-[15px] font-semibold" style={{ color: "var(--text-1)" }}>
        {formatEUR(point.value)}
      </p>
    </div>
  );
}

export function NetWorthChart() {
  const [period, setPeriod] = useState<Period>("1A");
  const [hoverValue, setHoverValue] = useState<number | null>(null);
  const { data: apiHistory } = useNetWorthHistory(365);

  // Use API data or generate fixtures
  const rawHistory = useMemo(() => {
    if (apiHistory && apiHistory.length > 0) return apiHistory;
    return generateNetWorthHistory(365);
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
            Patrimoine net
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
        <AreaChart
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
          <defs>
            <linearGradient id="netWorthGradient" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor={isPositive ? "#1fc090" : "#e54949"}
                stopOpacity={0.25}
              />
              <stop
                offset="100%"
                stopColor={isPositive ? "#1fc090" : "#e54949"}
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
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
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: "var(--text-6)" }}
            width={44}
          />
          <ReferenceLine y={startValue} stroke="var(--border-1)" strokeDasharray="4 4" />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{
              stroke: "var(--text-5)",
              strokeWidth: 1,
              strokeDasharray: "4 4",
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={isPositive ? "#1fc090" : "#e54949"}
            strokeWidth={1.5}
            fill="url(#netWorthGradient)"
            dot={false}
            activeDot={{
              r: 4,
              fill: isPositive ? "#1fc090" : "#e54949",
              stroke: "var(--bg-3)",
              strokeWidth: 2,
            }}
            animationDuration={800}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
