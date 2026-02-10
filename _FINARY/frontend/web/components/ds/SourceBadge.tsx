"use client";

type Source = "live" | "scraped" | "estimate" | "mock" | "computed" | "official" | "hardcoded" | "manual";

interface Props {
  source: Source;
  className?: string;
}

const CONFIG: Record<Source, { label: string; color: string; bg: string }> = {
  live:       { label: "Live",     color: "var(--green)",      bg: "var(--green-bg)" },
  scraped:    { label: "Scrapé",   color: "var(--blue)",       bg: "rgba(86,130,242,0.12)" },
  estimate:   { label: "Estimé",   color: "var(--orange)",     bg: "var(--orange-bg)" },
  computed:   { label: "Calculé",  color: "var(--accent)",     bg: "var(--accent-bg)" },
  official:   { label: "Officiel", color: "var(--blue-light)", bg: "rgba(86,130,242,0.12)" },
  hardcoded:  { label: "Fixe",     color: "var(--text-5)",     bg: "var(--bg-hover)" },
  manual:     { label: "Manuel",   color: "var(--orange)",     bg: "var(--orange-bg)" },
  mock:       { label: "Mock",     color: "var(--red)",        bg: "var(--red-bg)" },
};

export function SourceBadge({ source, className = "" }: Props) {
  const c = CONFIG[source] ?? CONFIG.mock;
  return (
    <span
      className={`inline-flex items-center gap-1 text-[9px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded ${className}`}
      style={{ color: c.color, background: c.bg }}
    >
      <span className="w-1 h-1 rounded-full" style={{ background: c.color }} />
      {c.label}
    </span>
  );
}
