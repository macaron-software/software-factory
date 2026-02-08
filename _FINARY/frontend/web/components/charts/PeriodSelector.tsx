"use client";

export type Period = "1M" | "3M" | "6M" | "YTD" | "1A" | "MAX";

const PERIODS: Period[] = ["1M", "3M", "6M", "YTD", "1A", "MAX"];

interface Props {
  selected: Period;
  onChange: (p: Period) => void;
}

export function PeriodSelector({ selected, onChange }: Props) {
  return (
    <div className="flex items-center gap-1 p-1 rounded-lg" style={{ background: "var(--bg-hover)" }}>
      {PERIODS.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className="tnum px-3 py-1.5 text-[11px] font-medium tracking-[0.02em] rounded-md transition-all"
          style={{
            background: selected === p ? "var(--bg-3)" : "transparent",
            color: selected === p ? "var(--text-1)" : "var(--text-5)",
            boxShadow: selected === p ? "0 1px 3px rgba(0,0,0,0.3)" : "none",
          }}
        >
          {p}
        </button>
      ))}
    </div>
  );
}

/** Compute days from period string. */
export function periodToDays(p: Period): number {
  switch (p) {
    case "1M": return 30;
    case "3M": return 90;
    case "6M": return 180;
    case "YTD": {
      const now = new Date();
      const jan1 = new Date(now.getFullYear(), 0, 1);
      return Math.ceil((now.getTime() - jan1.getTime()) / 86400000);
    }
    case "1A": return 365;
    case "MAX": return 9999;
  }
}
