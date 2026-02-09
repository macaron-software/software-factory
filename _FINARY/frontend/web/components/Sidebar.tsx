"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

interface NavItem {
  href: string;
  label: string;
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    items: [
      { href: "/", label: "Patrimoine" },
      { href: "/portfolio", label: "Portfolio" },
      { href: "/insights", label: "Insights" },
      { href: "/budget", label: "Budget" },
    ],
  },
  {
    title: "Investing",
    items: [
      { href: "/portfolio/stocks", label: "Actions & Fonds" },
      { href: "/immobilier", label: "Immobilier" },
    ],
  },
  {
    title: "Finances",
    items: [
      { href: "/loans", label: "Crédits" },
      { href: "/costs", label: "Coûts & Frais" },
    ],
  },
  {
    title: "Tools",
    items: [
      { href: "/tools/wealth-statement", label: "Déclaration patrimoine" },
      { href: "/accounts", label: "Comptes" },
    ],
  },
];

function FinaryLogo() {
  return (
    <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
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
    if (diffH < 1) return "Il y a moins d'1h";
    if (diffH < 24) return `Aujourd'hui, ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
    return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  })();

  const liveLabel = status?.live_prices ? `${status.live_prices} prix live` : null;

  return (
    <aside className="w-[220px] shrink-0 flex flex-col bg-bg-1 border-r border-bd-1">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-14">
        <FinaryLogo />
        <span className="text-title font-semibold text-t-1">finary</span>
      </div>

      {/* Nav sections */}
      <nav className="flex-1 px-3 mt-1 space-y-4">
        {SECTIONS.map((section, si) => (
          <div key={si}>
            {section.title && (
              <p className="text-caption font-medium uppercase px-3 mb-1 text-t-6">
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center h-9 px-3 rounded-lg text-body font-medium transition-colors ${
                      isActive ? "text-t-1 bg-bg-3" : "text-t-5 hover:bg-bg-hover"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-bd-1">
        <p className="text-label text-t-5">Dernière sync</p>
        <p className={`text-label mt-0.5 ${status?.stale ? "text-loss" : "text-t-6"}`}>
          {syncLabel}
        </p>
        {liveLabel && (
          <p className="text-label mt-0.5 text-accent">{liveLabel}</p>
        )}
      </div>
    </aside>
  );
}
