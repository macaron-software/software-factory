"use client";

import { formatEUR } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  label: string;
  value: number;
  valueColor?: string;
  suffix?: string;
  right?: ReactNode;
}

export function PageHeader({ label, value, valueColor, suffix, right }: Props) {
  return (
    <div className="flex items-end justify-between">
      <div>
        <p className="text-label font-medium uppercase mb-2 text-t-5">{label}</p>
        <p className={`tnum text-hero font-extralight tracking-tight ${valueColor ?? "text-t-1"}`}>
          {formatEUR(value)}
          {suffix && <span className="text-title font-normal text-t-5">{suffix}</span>}
        </p>
      </div>
      {right && <div className="text-right">{right}</div>}
    </div>
  );
}
