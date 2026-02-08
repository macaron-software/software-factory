"use client";

import { formatEUR, formatPct, pnlColor } from "@/lib/utils";

interface Props {
  label: string;
  value: number;
  variation?: number | null;
  negative?: boolean;
}

export function NetWorthCard({ label, value, variation, negative }: Props) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p
        className={`text-2xl font-bold mt-1 ${negative ? "text-red-600" : "text-gray-900"}`}
      >
        {formatEUR(value)}
      </p>
      {variation !== undefined && variation !== null && (
        <p className={`text-sm mt-1 ${pnlColor(variation)}`}>
          {formatPct(variation)}
        </p>
      )}
    </div>
  );
}
