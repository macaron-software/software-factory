---
name: dashboard-ui
description: "Next.js 14 dashboard components for Finary-style wealth management. Dark theme design system extracted from Finary production CSS. Covers net worth, portfolio, budget views with Recharts, TanStack Query, Zustand, Tailwind CSS."
---

# Dashboard UI — Finary Design System

## Design Tokens (from app.finary.com production CSS)

### Colors

```css
/* Background scale (darkest → lightest) */
--bg-0: #000000;    /* html */
--bg-1: #0e0e0f;    /* sidebar */
--bg-2: #131314;    /* main content area */
--bg-3: #1d1d1f;    /* cards / surfaces */
--bg-hover: hsla(220, 5%, 45%, 0.1);
--bg-active: hsla(220, 5%, 45%, 0.2);

/* Borders */
--border-1: #2e2f33;  /* subtle */
--border-2: #3e4147;  /* visible */

/* Text scale */
--text-1: #edf0f5;   /* primary / headings */
--text-2: #ced0d6;   /* secondary values */
--text-3: #adb0b8;   /* labels */
--text-4: #969ba3;   /* section titles */
--text-5: #6e727a;   /* captions / muted */
--text-6: #3e4147;   /* disabled */

/* Brand gold */
--accent: #f1c086;
--accent-2: #edb068;
--gradient: linear-gradient(115.79deg, #5682f2 -36.05%, #f9d09f 100.05%);

/* Semantic */
--green: #1fc090;   --green-bg: #083226;
--red: #e54949;     --red-bg: #3c1313;
--orange: #f49352;  --orange-bg: #402715;
--blue: #5682f2;

/* Chart palette (10 colors) */
#6f50e5 #d6475d #f49352 #486df0 #3c898e #f08696 #9c86f0 #90a5f0 #75cbd1 #f1c086
```

### Typography

- **Font**: Inter (weights 200, 400, 500, 600, 700)
- **Numbers**: `font-feature-settings: "tnum"; font-variant: tabular-nums;` — use `.tnum` class
- **Heading**: 40px font-extralight (net worth), 32px font-extralight (page titles)
- **Body**: 13px (default text), 14px (values)
- **Caption**: 11px tracking-[0.04em] uppercase (column headers, labels)
- **Letter spacing**: 0 (body), 0.02em (subtitles), 0.04em (labels)

### Spacing

Finary uses: 0, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64px

### Radius

- `--radius-sm: 4px` (tags, small elements)
- `--radius-md: 8px` (tooltips, inputs)
- `--radius-lg: 16px` (cards)
- `--radius-pill: 1000px` (badges, bar fills)

### Components

**Card**: `.card` class → `bg: var(--bg-3)`, `border: 1px solid var(--border-1)`, `border-radius: 16px`
**Tags**: `.tag-green` (gain), `.tag-red` (loss), `.tag-accent` (badge)
**Progress bars**: `.bar-track` + `.bar-fill`
**Spinner**: `.spinner` (gold accent, no indigo)

## Stack

- **Next.js 14** (App Router)
- **TanStack Query** (data fetching + cache)
- **Recharts** (charts)
- **Zustand** (state)
- **Tailwind CSS** (utility layout, never for colors — use CSS vars)

## Rules

1. **NEVER use Tailwind color classes** (`text-slate-*`, `bg-indigo-*`, etc.) — always use CSS variables via `style={{ color: "var(--text-X)" }}`
2. **NEVER use emojis** — the user hates them
3. **Always use `.tnum`** class on financial numbers
4. **Always use `.card`** class for surface containers
5. **Use `font-extralight` (200)** for large numbers (net worth, totals)
6. **Use `font-medium` (500)** for values in tables and lists
7. **PnL colors**: `var(--green)` for gain, `var(--red)` for loss, `var(--text-5)` for zero
8. **PnL badges**: colored background (`var(--green-bg)`) + text (`var(--green)`)

## Layout

```
app/
├── layout.tsx              # Sidebar (220px, bg-1) + main content (bg-2, max-w-960)
├── page.tsx                # Dashboard: net worth (40px extralight) + KPI grid + charts
├── portfolio/page.tsx      # Positions table with hover rows
├── accounts/page.tsx       # Grouped by institution
└── budget/page.tsx         # Bar chart + category breakdown
```

## API Hooks Pattern

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useNetWorth() {
  return useQuery({
    queryKey: ["networth"],
    queryFn: () => fetchApi<NetWorth>("/api/v1/networth"),
    staleTime: 5 * 60 * 1000,
  });
}
```
