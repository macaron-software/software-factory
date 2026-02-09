"use client";

import { formatEUR } from "@/lib/utils";

type Tone = "default" | "accent" | "negative" | "positive";

const toneColor: Record<Tone, string> = {
  default: "text-t-1",
  accent: "text-accent",
  negative: "text-loss",
  positive: "text-gain",
};

interface Props {
  label: string;
  value: number;
  tone?: Tone;
  detail?: string;
  color?: string;
}

export function StatCard({ label, value, tone = "default", detail, color }: Props) {
  return (
    <div className="bg-bg-hover p-5 rounded-lg">
      <div className="flex items-center gap-2 mb-2">
        {color && <div className="w-2 h-2 rounded-sm shrink-0" style={{ backgroundColor: color }} />}
        <p className="text-caption font-medium uppercase text-t-5">{label}</p>
      </div>
      <p className={`tnum text-heading font-semibold ${toneColor[tone]}`}>{formatEUR(value)}</p>
      {detail && <p className="text-label text-t-5 mt-1.5">{detail}</p>}
    </div>
  );
}
