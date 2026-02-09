"use client";

import type { ReactNode } from "react";

interface Props {
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function Section({ title, children, footer, className }: Props) {
  return (
    <div className={`card p-6 ${className ?? ""}`}>
      {title && (
        <h3 className="text-label font-medium uppercase text-t-5 mb-5">{title}</h3>
      )}
      {children}
      {footer && (
        <div className="flex items-center justify-between pt-4 mt-4 border-t border-bd-1">
          {footer}
        </div>
      )}
    </div>
  );
}
