"use client";

import { formatEUR, CHART_COLORS } from "@/lib/utils";

interface Props {
  institutions: { name: string; display_name: string; total: number }[];
}

export function InstitutionBar({ institutions }: Props) {
  const data = institutions
    .filter((i) => i.total !== 0)
    .sort((a, b) => Math.abs(b.total) - Math.abs(a.total));

  const maxVal = Math.max(...data.map((d) => Math.abs(d.total)));

  return (
    <div className="card p-6">
      <h3 className="text-[13px] font-medium mb-5" style={{ color: "var(--text-4)" }}>
        Par etablissement
      </h3>
      <div className="space-y-4">
        {data.map((inst, i) => {
          const pct = maxVal > 0 ? (Math.abs(inst.total) / maxVal) * 100 : 0;
          const color = inst.total < 0 ? "var(--red)" : CHART_COLORS[i % CHART_COLORS.length];
          return (
            <div key={inst.name}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[13px]" style={{ color: "var(--text-3)" }}>
                  {inst.display_name}
                </span>
                <span
                  className="tnum text-[13px] font-medium"
                  style={{ color: inst.total < 0 ? "var(--red)" : "var(--text-1)" }}
                >
                  {formatEUR(inst.total)}
                </span>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.7 }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
