# Finary — Personal Wealth Management Clone

## Architecture

Three-layer system: **scrapers** (Python) → **JSON/DuckDB files** → **API server** (Python/FastAPI) → **frontend** (Next.js).

```
scrapers/          Python CDP scrapers → scrapers/data/*.json + finary.duckdb
backend/           FastAPI API (:8000) reads from scrapers/data/
  api_server.py    Main API — all endpoints, reads JSON + DuckDB
  insights_engine.py  Budget aggregation, diversification, projections
  src/             Rust/Axum backend (planned, not active)
frontend/web/      Next.js 14 app (:3000) → calls API at :8000
```

The **active backend is `backend/api_server.py`** (Python/FastAPI), not the Rust code in `backend/src/`. The Rust backend (`Cargo.toml`, `src/main.rs`) is scaffolded but not serving traffic. The Python API reads directly from JSON files in `scrapers/data/` and from DuckDB at `scrapers/data/finary.duckdb`.

### Data flow

1. **Chrome** runs on port 18800 (real Chrome, not Chrome for Testing) with bank tabs open
2. **Scrapers** connect via CDP (Chrome DevTools Protocol) websockets to extract data
3. Scraped data lands in `scrapers/data/` as dated JSON files (e.g., `patrimoine_complet_2026-02-09.json`)
4. **Transactions** are stored in DuckDB (`scrapers/data/finary.duckdb`)
5. **API server** reads these files on each request — no separate database for the API
6. **Frontend** fetches from the API with TanStack Query hooks (`lib/hooks/useApi.ts`)

### Session keepalive

Bank sessions expire quickly. `scrapers/session_keepalive.py` runs as a daemon doing `Page.reload()` on every bank tab every 5 minutes via CDP. This is the only reliable way to keep sessions alive — `fetch(HEAD)` pings do not work.

## Commands

```bash
# Start everything (browser + API + frontend + keepalive)
./start.sh
./start.sh --stop

# API server (Python)
cd _FINARY && PYTHONPATH=. python3 backend/api_server.py
# Logs: /tmp/finary-api.log

# Frontend
cd frontend/web && npm run dev          # development
cd frontend/web && npm run build && npm start  # production
cd frontend/web && npm run lint         # ESLint
cd frontend/web && npm test             # Vitest (all)
cd frontend/web && npx vitest run __tests__/utils.test.ts  # single test

# Scrapers
cd scrapers && python -m pytest tests/                     # all tests
cd scrapers && python -m pytest tests/test_categorizer.py  # single test
cd scrapers && python -m pytest tests/test_categorizer.py::test_name -v  # single case
cd scrapers && ruff check .             # lint

# Rust backend (not active, but buildable)
cd backend && cargo build
cd backend && cargo test
cd backend && cargo test test_name
cd backend && cargo fmt --check && cargo clippy

# Infrastructure
docker compose up -d   # PostgreSQL (:5434) + Redis (:6381)
```

## Scraping via CDP

All scrapers connect to Chrome on `http://localhost:18800` via the DevTools Protocol. Pattern:

```python
import json, urllib.request, websockets

targets = json.loads(urllib.request.urlopen("http://localhost:18800/json/list").read())
page = next(t for t in targets if "bourso" in t["url"] and t["type"] == "page")

async with websockets.connect(page["webSocketDebuggerUrl"]) as ws:
    await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
        "expression": "document.title", "returnByValue": True
    }}))
    result = json.loads(await ws.recv())
```

**Critical**: Use real Chrome (`/Applications/Google Chrome.app`), never Chrome for Testing. CA and other banks block Chrome for Testing via TLS fingerprinting. See `scrapers/BROWSER.md`.

### Cookie extraction

- **Boursobank**: `Network.getCookies` with `urls: ["https://clients.boursobank.com"]`
- **Crédit Agricole**: `Network.getCookies` with `urls: ["https://dcam.credit-agricole.fr"]` (not `Storage.getCookies`)
- **CA BFF API**: `https://dcam.credit-agricole.fr/ca-languedoc/bff01/credits/{uuid}/`

## Key conventions

### Data integrity

**Never guess, compute, or estimate financial values.** All data must be either:
- `"scraped"` — extracted from bank websites/APIs
- `"official"` — from official published rates

Every loan/rate object must include a `rate_source` field. Never use `"computed"` or `"estimated"`.

### Amounts

- `DECIMAL(15,2)` in SQL, never floats for money
- Multi-currency: EUR primary, USD/GBP via ECB daily rates
- Bourso CSV amounts use French format: `−1 262,79` (U+2212 minus, narrow no-break spaces, comma decimal)

### Frontend design system

Dark theme matching Finary's production CSS. Tokens defined as CSS custom properties in `globals.css`:
- Backgrounds: `--bg-0` through `--bg-3`
- Text: `--text-1` (brightest) through `--text-6` (dimmest)
- Semantic: `--green` / `--red` for gain/loss
- Accent: `--accent` (gold, `#f1c086`)

Tailwind maps these via `tailwind.config.js`: use `bg-bg-2`, `text-t-1`, `text-gain`, `border-bd-1`, etc.

Shared DS components live in `components/ds/` (Badge, PageHeader, Section, StatCard). Use `formatEUR()` from `lib/utils.ts` for currency display.

### Frontend data fetching

API hooks in `lib/hooks/useApi.ts` wrap TanStack Query. Pages use API data with fixture fallbacks:

```tsx
const { data: apiData } = useMonthlyBudget(12);
const data = useMemo(() => apiData?.length ? apiData : generateFixtures(12), [apiData]);
```

### DuckDB

Transaction storage at `scrapers/data/finary.duckdb`. Tables:
- `transactions` — bank transactions (id, date, description, amount, category, bank, account)
- `snapshots` — daily patrimoine snapshots
- `market_prices` — daily ticker prices

`insights_engine.py`'s `load_transactions()` reads from DuckDB first, falls back to JSON.

### Commit messages

Format: `<type>(<scope>): <description>` — e.g., `feat(scrapers): add CA BFF API rate scraping`

### Language

UI is in French. Code comments and API keys are in English.
