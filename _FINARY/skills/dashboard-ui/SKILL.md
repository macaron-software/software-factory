---
name: dashboard-ui
description: Next.js 14 dashboard components for personal finance visualization. Use when building or modifying the web frontend. Covers net worth charts, portfolio allocation donuts, transaction lists, budget views, and responsive design with TanStack Query, Recharts, Zustand, and Tailwind CSS.
---

# Dashboard UI

Composants Next.js pour le dashboard patrimoine.

## Stack

- **Next.js 14** (App Router)
- **TanStack Query** (data fetching + cache)
- **Recharts** (graphiques)
- **Zustand** (state management)
- **Tailwind CSS** (styling)
- **date-fns** (dates)

## API Hooks Pattern

```typescript
import { useQuery } from "@tanstack/react-query";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Hooks par domaine
export function useNetWorth() {
  return useQuery({
    queryKey: ["networth"],
    queryFn: () => fetchApi<NetWorth>("/api/v1/networth"),
    staleTime: 5 * 60 * 1000, // 5min
  });
}

export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: () => fetchApi<Account[]>("/api/v1/accounts"),
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: () => fetchApi<Portfolio>("/api/v1/portfolio"),
  });
}

export function useTransactions(accountId: string, cursor?: string) {
  return useQuery({
    queryKey: ["transactions", accountId, cursor],
    queryFn: () => fetchApi<PaginatedResponse<Transaction>>(
      `/api/v1/accounts/${accountId}/transactions?cursor=${cursor || ""}`
    ),
  });
}
```

## Composants Clés

### Net Worth Card

```typescript
// Composant principal du dashboard
// Affiche: valeur nette, variation, graphe sparkline
export function NetWorthCard() {
  const { data } = useNetWorth();
  // Variation jour/semaine/mois en € et %
  // Graphe Area chart (évolution)
  // Breakdown donut (classes d'actifs)
}
```

### Allocation Donut

```typescript
// Recharts PieChart pour répartition
// Props: data = [{name, value, pct, color}]
// Variantes: par classe, par établissement, par secteur, par géo
```

### Transaction List

```typescript
// Liste virtualisée (react-window si >1000 items)
// Catégorie avec icône + couleur
// Montant coloré (vert positif, rouge négatif)
// Infinite scroll via cursor pagination
// Possibilité de re-catégoriser (click → dropdown)
```

### Performance Chart

```typescript
// Line chart comparatif: portfolio vs benchmark
// Sélecteur période: 1M, 3M, 6M, YTD, 1A, MAX
// Tooltip avec valeur + variation
```

## Layout

```
app/
├── layout.tsx              # Sidebar navigation
├── page.tsx                # Dashboard (net worth + résumé)
├── accounts/
│   ├── page.tsx            # Liste comptes
│   └── [id]/page.tsx       # Détail + transactions
├── portfolio/
│   ├── page.tsx            # Positions consolidées
│   ├── allocation/page.tsx # Répartitions
│   └── dividends/page.tsx  # Calendrier dividendes
├── budget/
│   └── page.tsx            # Revenus/dépenses
├── real-estate/
│   └── page.tsx            # Biens immobiliers
└── settings/
    └── page.tsx            # Sync, institutions, OTP
```

## Design Tokens

```css
/* Couleurs finance */
--color-positive: #10B981;   /* vert gains */
--color-negative: #EF4444;   /* rouge pertes */
--color-neutral: #6B7280;    /* gris neutre */

/* Classes d'actifs */
--color-cash: #60A5FA;
--color-stocks: #34D399;
--color-bonds: #A78BFA;
--color-real-estate: #F59E0B;
--color-crypto: #F97316;

/* Formatage montants */
const formatAmount = (n: number, currency = "EUR") =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency }).format(n);

const formatPct = (n: number) =>
  new Intl.NumberFormat("fr-FR", { style: "percent", minimumFractionDigits: 2 }).format(n / 100);
```
