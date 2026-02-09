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
      <p className="text-label font-medium uppercase text-t-5">{label}</p>
      <p className={`tnum text-xl font-semibold mt-2 ${negative ? "text-loss" : "text-t-1"}`}>
        {formatEUR(value)}
      </p>
      {variation !== undefined && variation !== null && (
        <span
          className={`tnum inline-block text-label font-medium mt-2 px-2 py-0.5 rounded ${
            variation >= 0 ? "bg-gain-bg text-gain" : "bg-loss-bg text-loss"
          }`}
        >
          {variation >= 0 ? "+" : ""}{variation.toFixed(2)}%
        </span>
      )}
    </div>
  );
}
