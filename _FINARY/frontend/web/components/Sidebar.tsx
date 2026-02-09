"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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

  return (
    <aside
      className="w-[220px] shrink-0 flex flex-col"
      style={{ background: "var(--bg-1)", borderRight: "1px solid var(--border-1)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-14">
        <FinaryLogo />
        <span className="text-[15px] font-semibold" style={{ color: "var(--text-1)" }}>
          finary
        </span>
      </div>

      {/* Nav sections */}
      <nav className="flex-1 px-3 mt-1 space-y-4">
        {SECTIONS.map((section, si) => (
          <div key={si}>
            {section.title && (
              <p
                className="text-[10px] font-medium tracking-[0.06em] uppercase px-3 mb-1"
                style={{ color: "var(--text-6)" }}
              >
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
                    className="flex items-center h-9 px-3 rounded-lg text-[13px] font-medium transition-colors"
                    style={{
                      color: isActive ? "var(--text-1)" : "var(--text-5)",
                      background: isActive ? "var(--bg-3)" : "transparent",
                    }}
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
      <div className="px-5 py-4" style={{ borderTop: "1px solid var(--border-1)" }}>
        <p className="text-[11px]" style={{ color: "var(--text-5)" }}>
          Derniere sync
        </p>
        <p className="text-[11px] mt-0.5" style={{ color: "var(--text-6)" }}>
          Aujourd&apos;hui, 08:00
        </p>
      </div>
    </aside>
  );
}
