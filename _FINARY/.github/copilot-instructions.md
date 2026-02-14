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

## SCA La Désirade

SCA attribution L.212-1 CCH. Legland 50,6% / Beaussier 49,4%. Capital 695 873€. Dissolution auto 06/09/2026. Grabels.
Avocats: Me Axel Saint Martin (SCA+Legland) vs Me Vernhet (Beaussier). Mandataire ad'hoc: Me Sandian (AMAJ, 1 800€). Expert: Philippe Combes (architecte DPLG).
Statuts: Art.18 (AF), Art.19 (défaillance AF → vente forcée, AG 2/3 hors défaillant), Art.36 (dissolution: personnalité morale survit, pas indivision, partage limité associés en règle, passif proportionnel indéfiniment)
CCA vs AF: Beaussier payait fournisseurs direct depuis perso → comptabilisé CCA (prêt remboursable) pas AF (contribution définitive). EC doit trancher. Art.19 = AF uniquement.
Dettes Beaussier: AF 25K€, capital non libéré 192K€, QP fournisseurs 11K€, travaux Combes 45K€, indemnité occupation ~1K€/mois. Total ~140-154K€ hors capital.
Vernhet: implication ~2/10. Conclusions vides (5p vs 17p Axel), écrit "SCI" au lieu de "SCA", pas de réponse art.28 (unanimité présents), 40K€ sans chiffrage ni dispositif, LRAR sans assignation. Phase 3 (minimum syndical, probablement impayé). Beaussier croit dissolution = libération (faux art.36).
8 proc: expertise ✅ (Combes), fond (Beaussier demanderesse — reconventionnelle à déposer par Axel: fautes gestion + AF + Combes + occupation + obstruction = ~112K€), appel HAH (délibéré 31/03, confirmation quasi certaine vu conclusions vides), nullité AG, expulsion JCP (reportée mai→juillet), prolongation, TA arrêté, art.19
Art.28 statuts = argument massue: AGO unanimité des PRÉSENTS. Beaussier ne vient pas → Legland vote seul = unanimité. Abus de majorité impossible (1ère instance + Axel l'a démontré).
Actions fév 2026: ✅ permis modificatif déposé mi-janv, ✅ EC contacté FEC transmis, ⏳ AG comptes (EC), ⏳ mise en demeure art.19 (huissier), ⏳ AG art.19, ⏳ prolongation 2 ans (abus minorité → judiciaire), ⏳ reconventionnelle au fond (après EC + appel), banque reporte prêt
Calendrier: mars-avril permis obtenu→AIT levé, 31/03 délibéré appel, avril AG comptes, mai AG art.19 + reconventionnelle, été travaux lot Legland
Factures Axel: 9 factures SCA/Perso. Estimation frais Vernhet: 22-39K€. Art.700 cumulés: 2K€ (1ère instance) + ~4K€ (appel probable) = ~6K€ Beaussier doit.
Sources: FEC SCA, DuckDB Bourso, Outlook CDP, statuts `MAISON GRABELS/COMPTA SCA/STATUTS_SCA.txt`, jugements + conclusions `MAISON GRABELS/PROCEDURE JUDICIAIRE/`

## Situation perso

Trésorerie tendue: cash ~2K€, salaire ~3 500€/mois, charges ~2 650€/mois, marge ~850€. Prêts Bourso reportés 3 mois (→ avril). IBKR 58K€ liquidable si urgence.
Prêts: PAS CA 637€/mois, conso CA 74€/mois, PTZ différé, Bourso ~11€/mois (reporté).
Scolarité 2 enfants (lycée privé Montpellier): Nathaël 2 899€, Abigaëlle 2 725€. QP mère 33% / père 67%. Mère verse 127,66€/mois + avancé inscription Nathaël 140€ + voyage NY 1 500€. Septembre: fille potentiel école autre ville + chambre étudiante + prêt étudiant.
Objectif été: permis modificatif → AIT levé → fenêtres → emménagement Grabels → économie loyer ~700€/mois.

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
