"use client";

import { cn } from "@/lib/utils";

type Variant = "gain" | "loss" | "accent" | "warn" | "neutral";

const styles: Record<Variant, string> = {
  gain: "bg-gain-bg text-gain",
  loss: "bg-loss-bg text-loss",
  accent: "bg-accent-bg text-accent",
  warn: "bg-warn-bg text-warn",
  neutral: "bg-bg-hover text-t-4",
};

interface Props {
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
}

export function Badge({ children, variant = "neutral", className }: Props) {
  return (
    <span className={cn("text-caption font-medium px-2 py-0.5 rounded inline-block", styles[variant], className)}>
      {children}
    </span>
  );
}
