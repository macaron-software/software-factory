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

/** Color for positive/negative values — Finary exact. */
export function pnlColor(value: number): string {
  if (value > 0) return "text-[#1fc090]";
  if (value < 0) return "text-[#e54949]";
  return "text-[#6e727a]";
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

/** Chart color palette — Finary exact. */
export const CHART_COLORS = [
  "#6f50e5",
  "#d6475d",
  "#f49352",
  "#486df0",
  "#3c898e",
  "#f08696",
  "#9c86f0",
  "#90a5f0",
  "#75cbd1",
  "#f1c086",
];
