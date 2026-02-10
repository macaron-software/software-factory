"use client";

import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
}

export function DetailSheet({ open, onClose, title, subtitle, children }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-[2px] animate-fadeIn"
        onClick={onClose}
      />
      {/* Panel */}
      <div
        ref={panelRef}
        className="relative w-full max-w-[480px] h-full bg-bg-2 border-l border-bd-1 overflow-y-auto animate-slideIn"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 bg-bg-2 border-b border-bd-1 px-6 py-5 flex items-center justify-between">
          <div>
            <h2 className="text-title font-semibold text-t-1">{title}</h2>
            {subtitle && (
              <p className="text-label text-t-5 mt-0.5">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-t-5 hover:text-t-2 hover:bg-bg-hover transition-colors"
          >
            ✕
          </button>
        </div>
        {/* Content */}
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}
