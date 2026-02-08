/** Format a number as EUR currency. */
export function formatEUR(value: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/** Format a number as a given currency. */
export function formatCurrency(value: number, currency: string): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/** Format a percentage. */
export function formatPct(value: number, decimals = 2): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)} %`;
}

/** Format a number with thousand separators (fr-FR). */
export function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** Color for positive/negative values. */
export function pnlColor(value: number): string {
  if (value > 0) return "text-emerald-500";
  if (value < 0) return "text-red-500";
  return "text-gray-500";
}

/** Category labels in French. */
export const CATEGORY_LABELS: Record<string, string> = {
  alimentation: "Alimentation",
  restauration: "Restauration",
  transport: "Transport",
  abonnements: "Abonnements",
  telecom: "Télécom",
  logement: "Logement",
  energie: "Énergie",
  assurance: "Assurance",
  sante: "Santé",
  shopping: "Shopping",
  revenus: "Revenus",
  aides: "Aides",
  impots: "Impôts",
  epargne: "Épargne",
  frais_bancaires: "Frais bancaires",
  retrait: "Retrait DAB",
  investissement: "Investissement",
  non_categorise: "Non catégorisé",
};

/** Chart color palette for finance dashboards. */
export const CHART_COLORS = [
  "#10b981", // emerald-500
  "#3b82f6", // blue-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#06b6d4", // cyan-500
  "#f97316", // orange-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
  "#6366f1", // indigo-500
];
