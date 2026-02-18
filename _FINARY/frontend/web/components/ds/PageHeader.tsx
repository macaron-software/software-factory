"use client";

import { formatEURCompact } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  label: string;
  value?: number;
  valueColor?: string;
  suffix?: string;
  right?: ReactNode;
}

export function PageHeader({ label, value, valueColor, suffix, right }: Props) {
  return (
    <div className="flex items-end justify-between">
      <div>
        <p className="section-title mb-2">{label}</p>
        {value != null && (
          <p className={`num-hero ${valueColor ?? "text-t-1"}`}>
            {formatEURCompact(value)}
            {suffix && <span className="text-title font-normal text-t-5 ml-1">{suffix}</span>}
          </p>
        )}
      </div>
      {right && <div className="text-right">{right}</div>}
    </div>
  );
}
