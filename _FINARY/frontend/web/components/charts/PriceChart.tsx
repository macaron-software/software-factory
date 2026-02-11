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

interface ChartPoint {
  date: string;
  label: string;
  value: number;
}

interface Props {
  title: string;
  data: { date: string; value: number }[];
  height?: number;
  color?: string;
  defaultPeriod?: Period;
  /** Live value override — displayed instead of last chart point when not hovering */
  liveValue?: number;
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr);
  const months = ["Jan", "Fev", "Mar", "Avr", "Mai", "Jun", "Jul", "Aou", "Sep", "Oct", "Nov", "Dec"];
  return `${d.getDate()} ${months[d.getMonth()]}`;
}

function formatMonthLabel(dateStr: string): string {
  const d = new Date(dateStr);
  const months = ["Jan.", "Mar.", "Mai.", "Jul.", "Sep.", "Nov."];
  const idx = Math.floor(d.getMonth() / 2);
  return months[idx] || "";
}

/** Reusable Finary-style line chart. Used for portfolio, stocks, positions. */
export function PriceChart({ title, data, height = 280, color = "#5682f2", defaultPeriod = "1Y", liveValue }: Props) {
  const [period, setPeriod] = useState<Period>(defaultPeriod);
  const [hoverValue, setHoverValue] = useState<number | null>(null);

  const chartData = useMemo<ChartPoint[]>(() => {
    const days = periodToDays(period);
    const sliced = data.slice(-days);
    return sliced.map((d) => ({
      date: d.date,
      label: formatDateLabel(d.date),
      value: d.value,
    }));
  }, [data, period]);

  const currentValue = liveValue ?? chartData[chartData.length - 1]?.value ?? 0;
  const startValue = chartData[0]?.value ?? 0;
  const refValue = hoverValue ?? chartData[chartData.length - 1]?.value ?? currentValue;
  const variation = startValue > 0 ? ((refValue - startValue) / startValue) * 100 : 0;
  const variationAbs = refValue - startValue;
  const isPositive = variation >= 0;

  const tickInterval = useMemo(() => {
    if (chartData.length <= 7) return 1;
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

  const [yMin, yMax] = useMemo(() => {
    const values = chartData.map((d) => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.15 || 1;
    return [min - padding, max + padding];
  }, [chartData]);

  return (
    <div>
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-[11px] font-medium tracking-[0.04em] uppercase mb-1" style={{ color: "var(--text-5)" }}>
            {title}
          </p>
          <p className="tnum text-[28px] font-extralight tracking-tight leading-none" style={{ color: "var(--text-1)" }}>
            {formatEUR(currentValue)}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="tnum text-[13px] font-medium" style={{ color: isPositive ? "var(--green)" : "var(--red)" }}>
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

      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
          onMouseMove={(e) => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const payload = (e as any)?.activePayload;
            if (payload?.[0]) setHoverValue(payload[0].payload.value);
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
            tickFormatter={(v: number) => `€${Math.round(v).toLocaleString("fr-FR")}`}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: "var(--text-6)" }}
            width={72}
          />
          <Tooltip
            content={() => null}
            cursor={{ stroke: "var(--text-5)", strokeWidth: 1, strokeDasharray: "4 4" }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            fill="none"
            dot={false}
            activeDot={{ r: 4, fill: color, stroke: "var(--bg-3)", strokeWidth: 2 }}
            animationDuration={600}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
