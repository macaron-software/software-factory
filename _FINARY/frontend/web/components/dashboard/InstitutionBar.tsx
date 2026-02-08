"use client";

import { formatEUR, CHART_COLORS } from "@/lib/utils";

interface Props {
  institutions: { name: string; display_name: string; total: number }[];
}

const INSTITUTION_ICONS: Record<string, string> = {
  boursobank: "B",
  credit_agricole: "CA",
  ibkr: "IB",
  trade_republic: "TR",
};

export function InstitutionBar({ institutions }: Props) {
  const data = institutions
    .filter((i) => i.total !== 0)
    .sort((a, b) => Math.abs(b.total) - Math.abs(a.total));

  const totalAbs = data.reduce((s, d) => s + Math.abs(d.total), 0);

  return (
    <div className="card p-6">
      <h3 className="text-[11px] font-medium tracking-[0.04em] uppercase mb-5" style={{ color: "var(--text-5)" }}>
        Par etablissement
      </h3>
      <div className="space-y-4">
        {data.map((inst, i) => {
          const pct = totalAbs > 0 ? (Math.abs(inst.total) / totalAbs) * 100 : 0;
          const color = inst.total < 0 ? "var(--red)" : CHART_COLORS[i % CHART_COLORS.length];
          const icon = INSTITUTION_ICONS[inst.name] ?? inst.display_name.charAt(0);
          return (
            <div
              key={inst.name}
              className="flex items-center gap-4 py-2 px-2 -mx-2 rounded-lg transition-colors cursor-default"
              style={{ background: "transparent" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              {/* Icon */}
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0"
                style={{
                  background: `${color}20`,
                  color: color,
                }}
              >
                {icon}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] font-medium truncate" style={{ color: "var(--text-2)" }}>
                    {inst.display_name}
                  </span>
                  <span
                    className="tnum text-[13px] font-semibold ml-3"
                    style={{ color: inst.total < 0 ? "var(--red)" : "var(--text-1)" }}
                  >
                    {formatEUR(inst.total)}
                  </span>
                </div>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.6 }}
                  />
                </div>
              </div>

              {/* Percentage */}
              <span
                className="tnum text-[11px] font-medium w-[38px] text-right shrink-0"
                style={{ color: "var(--text-5)" }}
              >
                {pct.toFixed(0)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
