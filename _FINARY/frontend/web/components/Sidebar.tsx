"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  PieChart,
  Lightbulb,
  Wallet,
  TrendingUp,
  Home,
  CreditCard,
  Receipt,
  FileText,
  Building2,
  Wifi,
  WifiOff,
  Eye,
  EyeOff,
  type LucideIcon,
} from "lucide-react";
import { useAppStore } from "@/lib/store";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    items: [
      { href: "/", label: "Patrimoine", icon: LayoutDashboard },
      { href: "/portfolio", label: "Portfolio", icon: PieChart },
      { href: "/insights", label: "Insights", icon: Lightbulb },
      { href: "/budget", label: "Budget", icon: Wallet },
    ],
  },
  {
    title: "Investissements",
    items: [
      { href: "/portfolio/stocks", label: "Actions & Fonds", icon: TrendingUp },
      { href: "/immobilier", label: "Immobilier", icon: Home },
    ],
  },
  {
    title: "Finances",
    items: [
      { href: "/loans", label: "Crédits", icon: CreditCard },
      { href: "/costs", label: "Coûts & Frais", icon: Receipt },
    ],
  },
  {
    title: "Outils",
    items: [
      { href: "/tools/wealth-statement", label: "Déclaration", icon: FileText },
      { href: "/accounts", label: "Comptes", icon: Building2 },
    ],
  },
];

function FinaryLogo() {
  return (
    <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
      <defs>
        <linearGradient id="fg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#5682f2" />
          <stop offset="100%" stopColor="#f9d09f" />
        </linearGradient>
      </defs>
      <rect x="4" y="6" width="24" height="5" rx="2.5" fill="url(#fg)" />
      <rect x="4" y="14" width="16" height="5" rx="2.5" fill="url(#fg)" />
      <rect x="4" y="22" width="10" height="5" rx="2.5" fill="url(#fg)" opacity="0.7" />
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { privacyMode, togglePrivacy } = useAppStore();

  /* sync data-privacy attribute on mount (for SSR hydration) */
  React.useEffect(() => {
    document.documentElement.setAttribute("data-privacy", privacyMode ? "on" : "off");
  }, [privacyMode]);

  const { data: status } = useQuery({
    queryKey: ["status"],
    queryFn: () => fetch("http://localhost:8000/api/v1/status").then((r) => r.json()),
    refetchInterval: 60_000,
  });

  const syncLabel = (() => {
    if (!status?.data_timestamp) return "—";
    const d = new Date(status.data_timestamp);
    const now = new Date();
    const diffH = (now.getTime() - d.getTime()) / 3600000;
    if (diffH < 1) return "< 1h";
    if (diffH < 24) return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
  })();

  const liveCount = status?.live_prices ?? 0;
  const isLive = liveCount > 0;

  return (
    <aside
      className="w-[232px] shrink-0 flex flex-col border-r"
      style={{ background: "var(--bg-1)", borderColor: "var(--border-1)" }}
    >
      {/* ── Logo ── */}
      <div className="flex items-center gap-3 px-5 h-16">
        <FinaryLogo />
        <span
          className="text-[15px] font-semibold tracking-[-0.01em]"
          style={{ color: "var(--text-1)" }}
        >
          finary
        </span>
        <button
          onClick={togglePrivacy}
          title={privacyMode ? "Afficher les montants" : "Masquer les montants"}
          className="ml-auto flex items-center justify-center w-7 h-7 rounded-md transition-colors duration-150"
          style={{
            color: privacyMode ? "var(--accent)" : "var(--text-5)",
            background: privacyMode ? "var(--accent-dim)" : "transparent",
          }}
          onMouseEnter={(e) => {
            if (!privacyMode) e.currentTarget.style.background = "var(--bg-hover)";
          }}
          onMouseLeave={(e) => {
            if (!privacyMode) e.currentTarget.style.background = "transparent";
          }}
        >
          {privacyMode ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 px-3 mt-1 space-y-5 overflow-y-auto">
        {SECTIONS.map((section, si) => (
          <div key={si}>
            {section.title && (
              <p
                className="text-[10px] font-semibold uppercase tracking-[0.08em] px-3 mb-2"
                style={{ color: "var(--text-6)" }}
              >
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname === item.href || pathname.startsWith(item.href + "/");
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="group flex items-center gap-3 h-9 px-3 rounded-lg transition-all duration-150"
                    style={{
                      color: isActive ? "var(--text-1)" : "var(--text-4)",
                      background: isActive ? "var(--bg-3)" : "transparent",
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = "var(--bg-hover)";
                        e.currentTarget.style.color = "var(--text-2)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.color = "var(--text-4)";
                      }
                    }}
                  >
                    <Icon
                      size={16}
                      strokeWidth={isActive ? 2 : 1.5}
                      style={{
                        color: isActive ? "var(--accent)" : "currentColor",
                        opacity: isActive ? 1 : 0.7,
                      }}
                    />
                    <span
                      className="text-[13px] font-medium"
                      style={{ fontWeight: isActive ? 600 : 500 }}
                    >
                      {item.label}
                    </span>
                    {isActive && (
                      <div
                        className="ml-auto w-1.5 h-1.5 rounded-full"
                        style={{ background: "var(--accent)" }}
                      />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Status footer ── */}
      <div
        className="px-4 py-3 mx-3 mb-3 rounded-lg"
        style={{ background: "var(--bg-3)" }}
      >
        <div className="flex items-center gap-2 mb-1.5">
          {isLive ? (
            <Wifi size={12} style={{ color: "var(--green)" }} />
          ) : (
            <WifiOff size={12} style={{ color: "var(--text-6)" }} />
          )}
          <span
            className="text-[11px] font-medium"
            style={{ color: isLive ? "var(--green)" : "var(--text-5)" }}
          >
            {isLive ? "Connecté" : "Hors ligne"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px]" style={{ color: "var(--text-6)" }}>
            Sync: {syncLabel}
          </span>
          {isLive && (
            <span className="text-[10px] font-medium" style={{ color: "var(--accent-dim)" }}>
              {liveCount} live
            </span>
          )}
        </div>
      </div>
    </aside>
  );
}
