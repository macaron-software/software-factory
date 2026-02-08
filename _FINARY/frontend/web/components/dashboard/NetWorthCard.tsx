"use client";

import { formatEUR } from "@/lib/utils";

interface Props {
  label: string;
  value: number;
  variation?: number | null;
  negative?: boolean;
}

export function NetWorthCard({ label, value, variation, negative }: Props) {
  return (
    <div className="card px-5 py-4">
      <p className="text-[11px] font-medium tracking-[0.04em] uppercase" style={{ color: "var(--text-5)" }}>
        {label}
      </p>
      <p
        className="tnum text-xl font-semibold mt-2"
        style={{ color: negative ? "var(--red)" : "var(--text-1)" }}
      >
        {formatEUR(value)}
      </p>
      {variation !== undefined && variation !== null && (
        <span
          className="tnum inline-block text-[11px] font-medium mt-2 px-2 py-0.5 rounded"
          style={{
            background: variation >= 0 ? "var(--green-bg)" : "var(--red-bg)",
            color: variation >= 0 ? "var(--green)" : "var(--red)",
          }}
        >
          {variation >= 0 ? "+" : ""}{variation.toFixed(2)}%
        </span>
      )}
    </div>
  );
}
