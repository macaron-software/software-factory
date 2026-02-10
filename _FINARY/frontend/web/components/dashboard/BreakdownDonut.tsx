"use client";

import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Sector } from "recharts";
import { formatEUR, CHART_COLORS } from "@/lib/utils";
import { SourceBadge } from "@/components/ds";
import type { DataSource } from "@/lib/types/api";

interface Props {
  breakdown: {
    cash: number;
    savings: number;
    investments: number;
    real_estate: number;
  };
  onSliceClick?: (className: string) => void;
  sources?: Record<string, DataSource>;
}

const LABELS: Record<string, string> = {
  cash: "Liquidites",
  savings: "Epargne",
  investments: "Investissements",
  real_estate: "Immobilier",
};

const SOURCE_MAP: Record<string, string> = {
  cash: "cash",
  savings: "savings",
  investments: "investments",
  real_estate: "real_estate",
};

/* eslint-disable @typescript-eslint/no-explicit-any */
function ActiveShape(props: any) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props;
  return (
    <g>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius - 2}
        outerRadius={outerRadius + 3}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
      />
    </g>
  );
}

export function BreakdownDonut({ breakdown, onSliceClick, sources }: Props) {
  const [activeIndex, setActiveIndex] = useState<number>(-1);

  const data = Object.entries(breakdown)
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({
      key,
      name: LABELS[key] || key,
      value,
    }));

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="card p-6">
      <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-5" style={{ color: "var(--text-5)" }}>
        Repartition par classe
      </h3>
      <div className="flex items-center gap-8">
        <div className="w-[160px] h-[160px] shrink-0 relative">
          {/* Center value */}
          <div
            className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
            style={{ zIndex: 1 }}
          >
            <span className="tnum text-[15px] font-semibold" style={{ color: "var(--text-1)" }}>
              {formatEUR(activeIndex >= 0 ? data[activeIndex]?.value ?? total : total)}
            </span>
            <span className="text-[10px]" style={{ color: "var(--text-5)" }}>
              {activeIndex >= 0 ? data[activeIndex]?.name : "Total"}
            </span>
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={72}
                dataKey="value"
                stroke="var(--bg-3)"
                strokeWidth={2}
                startAngle={90}
                endAngle={-270}
                activeShape={ActiveShape}
                onMouseEnter={(_, i) => setActiveIndex(i)}
                onMouseLeave={() => setActiveIndex(-1)}
                animationBegin={0}
                animationDuration={800}
                animationEasing="ease-out"
              >
                {data.map((_, i) => (
                  <Cell
                    key={i}
                    fill={CHART_COLORS[i % CHART_COLORS.length]}
                    opacity={activeIndex >= 0 && activeIndex !== i ? 0.35 : 1}
                    style={{ transition: "opacity 0.2s" }}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-3">
          {data.map((d, i) => (
            <div
              key={d.name}
              className="flex items-center justify-between py-1 px-2 -mx-2 rounded-md transition-colors cursor-pointer"
              style={{
                background: activeIndex === i ? "var(--bg-hover)" : "transparent",
              }}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseLeave={() => setActiveIndex(-1)}
              onClick={() => onSliceClick?.(d.name)}
            >
              <div className="flex items-center gap-2">
                <div
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <span className="text-[13px]" style={{ color: "var(--text-3)" }}>{d.name}</span>
                {sources?.[SOURCE_MAP[d.key]] && <SourceBadge source={sources[SOURCE_MAP[d.key]]} />}
              </div>
              <div className="flex items-center gap-3">
                <span className="tnum text-[13px] font-medium" style={{ color: "var(--text-1)" }}>
                  {formatEUR(d.value)}
                </span>
                <span
                  className="tnum text-[11px] w-[42px] text-right font-medium px-1.5 py-0.5 rounded"
                  style={{
                    color: "var(--text-4)",
                    background: "var(--bg-hover)",
                  }}
                >
                  {((d.value / total) * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
