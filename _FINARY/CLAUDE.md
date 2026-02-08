# FINARY — Personal Wealth Management

## Projet

Clone Finary pour usage personnel. Agrégation IBKR, Trade Republic, Boursobank, Crédit Agricole (perso + pro).

## Stack

- **Scrapers** : Python 3.12+ / Playwright / httpx
- **Backend** : Rust (Axum) + SQLx + PostgreSQL 15 + Redis
- **Web** : Next.js 14 + TanStack Query + Recharts + Tailwind
- **Mobile** : SwiftUI (iOS) + Jetpack Compose (Android)

## Commandes

```bash
# Scrapers
cd scrapers && python -m pytest tests/
cd scrapers && python scheduler.py              # Run sync

# Backend
cd backend && cargo build
cd backend && cargo test
cd backend && cargo test test_name              # Single test
cd backend && cargo fmt --check && cargo clippy

# Web
cd frontend/web && npm run dev
cd frontend/web && npm run test
cd frontend/web && npm run lint && npm run type-check

# DB
cd backend && sqlx migrate run
```

## Skills

6 skills dans `skills/` (format Anthropic SKILL.md) :
- `bank-scraper` : Scraping Playwright + API
- `rust-api` : Backend Axum endpoints
- `finance-data` : Schéma DB + calculs financiers
- `dashboard-ui` : Composants Next.js
- `mobile-finance` : SwiftUI + Compose
- `e2e-scraper` : Tests scrapers

## Conventions

- **Montants** : DECIMAL(15,2), jamais de float
- **Devises** : Multi-devise (EUR, USD, GBP), conversion ECB
- **Timestamps** : UTC partout, conversion côté client
- **Credentials** : AES-256-GCM, jamais en clair
- **Commit** : `<type>(<scope>): <description>`
