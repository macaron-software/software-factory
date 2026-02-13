# Finary — Personal Wealth Management

## Stack

```
scrapers/        Python CDP → Chrome:18800 → scrapers/data/*.json + finary.duckdb
backend/         api_server.py (FastAPI :8000) — reads JSON+DuckDB, ~1870L
                 insights_engine.py — budget aggregation, diversification, projections
                 src/ — Rust/Axum scaffolded, NOT active
frontend/web/    Next.js 14 (:3000) — TanStack Query → API :8000
```

## Data flow

Chrome:18800 (real, NOT Chrome for Testing) → CDP scrapers → dated JSON + DuckDB → API reads on request → frontend hooks

Banks: Boursobank, Crédit Agricole (perso+pro), IBKR, Trade Republic
Session keepalive: `session_keepalive.py` daemon — Page.reload() every 5min via CDP

## Pages (frontend/web/app/)

| Page | Endpoint | Description |
|------|----------|-------------|
| `/` | `/patrimoine` | Dashboard patrimoine — net worth, allocation |
| `/accounts` | `/accounts` | Comptes bancaires détaillés |
| `/portfolio` | `/portfolio`, `/portfolio/allocation`, `/portfolio/dividends` | Portefeuille titres IBKR+TR |
| `/budget` | `/budget/monthly`, `/budget/categories`, `/budget/projections` | Budget mensuel, catégories, projections M+1/+2/+3 |
| `/loans` | `/loans`, `/loans/analysis` | Crédits immobiliers + analyse inflation |
| `/costs` | `/costs` | Frais récurrents + analyse fees |
| `/insights` | `/insights/rules` | Recommandations financières rules-based |
| `/immobilier` | `/patrimoine/projection` | Projections patrimoine immobilier |
| `/sca` | `/sca`, `/sca/legal` | SCA La Désirade — projet, procédures judiciaires |

## API endpoints (34 total)

`/api/v1/` prefix. Key: patrimoine, networth(/history), accounts(/{id}, /{id}/transactions), portfolio(/allocation, /dividends), budget(/monthly, /categories, /categories/{cat}/transactions, /projections), loans(/analysis), costs, insights/rules, sca(/legal), market(/fx, /quote/{t}, /history/{t}, /sparklines, /refresh), transactions, alerts, analytics/diversification, reload, status

## DS components (frontend/web/components/ds/)

Badge, DetailSheet, Feedback, PageHeader, Section, SourceBadge, StatCard
Charts: recharts (BarChart, PieChart, AreaChart)
Icons: lucide-react (Gavel, Scale, Clock, AlertCircle, CheckCircle, etc.)

## Design tokens (globals.css → tailwind)

Dark theme. `--bg-0..3`, `--text-1..6`, `--green`/`--red` gain/loss, `--accent` gold #f1c086
Tailwind: `bg-bg-2`, `text-t-1`, `text-gain`, `text-loss`, `border-bd-1`

## SCA La Désirade — Legal tracking

8 procédures: expertise (terminée, Philippe Combes), fond (en attente), appel HAH RG 25/04363 (CA Montpellier, délibéré 31/03), nullité AG 17/03/2025, référé expulsion JCP, prolongation SCA, recours TA arrêté (Grabels), vente forcée art.19
Factures Me Saint Martin: 9 factures (SCA/Perso tags, payée/impayée), totaux avec montants inconnus
Estimation frais Beaussier (Me Vernhet): 22-39K€, préjudices judiciaires détaillés (rapport expertise + conclusions)
Source données: FEC SCA (622600/401/512), DuckDB Bourso transactions, emails Outlook CDP

## Key files

| File | Lines | Role |
|------|-------|------|
| `backend/api_server.py` | ~1870 | ALL endpoints, SCA legal ~L1199-1665 |
| `backend/insights_engine.py` | ~300 | Budget aggregation, projections |
| `frontend/web/app/sca/page.tsx` | ~673 | SCA page — procedures, invoices, costs |
| `frontend/web/app/insights/page.tsx` | ~653 | Insights dashboard |
| `frontend/web/lib/hooks/useApi.ts` | ~212 | TanStack Query hooks for all endpoints |
| `frontend/web/lib/utils.ts` | ~105 | formatEUR, formatEURCompact, CHART_COLORS |
| `scrapers/scrape_cdp_v2.py` | - | Main CDP scraper (Bourso, CA, IBKR, TR) |
| `scrapers/data/finary.duckdb` | - | Transactions, snapshots, market_prices |

## Commands

```bash
./start.sh                    # Start all (Chrome + API + frontend + keepalive)
./start.sh --stop             # Stop all
PYTHONPATH=. python3 backend/api_server.py  # API only → /tmp/finary-api.log
cd frontend/web && npm run dev              # Frontend dev
cd frontend/web && npm test                 # Vitest
cd scrapers && python -m pytest tests/      # Scraper tests
cd scrapers && ruff check .                 # Lint
```

## Conventions

- **NEVER guess financial values** — scraped or official only, `rate_source` field mandatory
- DECIMAL(15,2) for money, never float
- Multi-currency EUR/USD/GBP via ECB rates
- Bourso CSV: French format `−1 262,79` (U+2212, NNBSP, comma decimal)
- Commits: `<type>(<scope>): <desc>` — e.g. `feat(sca): add nullité AG procedure`
- UI: French. Code: English.
- CDP: real Chrome only (banks block Chrome for Testing via TLS fingerprint)
- Cookie extraction: Bourso=Network.getCookies(clients.boursobank.com), CA=Network.getCookies(dcam.credit-agricole.fr)
