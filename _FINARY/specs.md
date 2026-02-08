# FINARY — Spécification Fonctionnelle

## 1. Vue d'ensemble

Application de gestion de patrimoine personnel, agrégation multi-établissements avec scraping.

**Utilisateur** : Single-user (usage personnel)
**Comptes connectés** :

| Établissement | Type | Comptes | Méthode |
|---|---|---|---|
| Interactive Brokers | Courtier international | Brokerage (actions, options, ETF) | Client Portal API |
| Trade Republic | Courtier EU | PEA, CTO (actions, ETF, crypto) | Playwright / WS |
| Boursobank | Banque + courtier | CC, Livrets, AV, PEA, CTO | Playwright |
| Crédit Agricole | Banque | CC perso, CC pro, Livrets, Crédits | Playwright |

## 2. Modules Fonctionnels

### 2.1 Patrimoine Global (Net Worth)

**Écran principal** — Vue synthétique de tout le patrimoine.

- **Valeur nette** = Total actifs - Total passifs
- **Graphe évolution** net worth sur 1M / 3M / 6M / 1A / MAX
- **Répartition par classe d'actifs** (donut chart) :
  - Liquidités (CC, livrets)
  - Actions (PEA, CTO, IBKR)
  - Obligations / Fonds euros
  - Immobilier
  - Crypto
  - Autres (métaux précieux, etc.)
- **Répartition par établissement** (bar chart)
- **Répartition géographique** (carte ou donut)
- **Variation** : jour, semaine, mois, année (€ et %)

### 2.2 Comptes Bancaires

- **Liste des comptes** avec solde actuel et variation
- **Détail compte** : historique transactions
- **Catégorisation automatique** des transactions :
  - Alimentation, Transport, Logement, Loisirs, Santé, Revenus, Épargne, Abonnements...
  - Règles regex + fallback LLM
  - Possibilité de re-catégoriser manuellement (apprentissage)
- **Solde prévisionnel** : projection fin de mois basée sur récurrences

### 2.3 Portfolio Investissement

- **Vue consolidée** : toutes positions tous comptes
- **Par position** :
  - Ticker, nom, quantité, PRU, cours actuel, P&L (€ et %), poids
  - Graphe cours + points d'achat/vente
- **Performance** :
  - TWR (Time-Weighted Return) et MWR (Money-Weighted Return)
  - Benchmark vs S&P500, CAC40, MSCI World
  - Performance par période (YTD, 1A, 3A, 5A, MAX)
- **Allocation** :
  - Par secteur (GICS)
  - Par géographie
  - Par devise
  - Par type (actions, ETF, obligations, crypto)
- **Dividendes** :
  - Calendrier des paiements à venir
  - Historique reçu
  - Rendement annuel estimé
  - Graphe dividendes mensuels/annuels

### 2.4 Budget & Cashflow

- **Revenus vs Dépenses** par mois (bar chart empilé)
- **Top catégories** de dépenses
- **Taux d'épargne** mensuel
- **Récurrences détectées** (abonnements, salaire, loyer)
- **Alertes** : dépense anormale, découvert prévu

### 2.5 Immobilier

- **Biens** : adresse, surface, type (RP, locatif, secondaire)
- **Valeur estimée** (API DVF / saisie manuelle)
- **Crédit associé** : capital restant dû, mensualité, taux
- **Rendement locatif** : brut et net
- **Plus-value latente** : prix achat vs valeur actuelle

### 2.6 Sync & Scraping

- **Sync automatique** : CRON 4x/jour (06h, 12h, 18h, 00h)
- **Sync manuelle** : bouton par établissement ou global
- **Status** : dernière sync, erreurs, OTP requis
- **Gestion OTP** :
  - TOTP automatique (si configuré)
  - Notification push pour OTP SMS (saisie manuelle)
- **Historique syncs** : succès/échecs avec logs

### 2.7 Market Data & Cours (Data Aggregation Layer)

Source de données de marché pour les cours temps-réel et historiques.

#### Providers (par priorité)

| Provider | Usage | Free Tier | Données |
|---|---|---|---|
| **Yahoo Finance** (yfinance) | Cours actions/ETF, historique | Illimité (non officiel) | Delayed 15min, historique daily |
| **Finnhub** | Cours temps-réel, dividendes, profil société | 60 calls/min | Real-time US, delayed EU |
| **ECB** (Banque Centrale Européenne) | Taux de change EUR/X | Illimité | Daily FX rates |
| **IBKR API** | Cours temps-réel (si connecté) | Avec compte IBKR | Real-time toutes bourses |

#### Pipeline d'enrichissement

```
Position scrapée (ticker + quantité + PRU)
    │
    ▼
[1] RÉSOLUTION ISIN ↔ TICKER
    │  • Table locale isin_ticker_map
    │  • Fallback: Yahoo Finance search API
    │  • Cache: permanent (ISIN ne change pas)
    │
    ▼
[2] COURS ACTUEL
    │  • Source primaire: yfinance (gratuit, fiable)
    │  • Fallback: Finnhub (si yfinance down)
    │  • Cache Redis: TTL 5min (heures marché), 1h (hors marché)
    │  • CRON refresh: toutes les 5min pendant heures d'ouverture
    │
    ▼
[3] HISTORIQUE COURS (daily OHLCV)
    │  • yfinance: historique complet gratuit
    │  • Stocké en DB: table price_history
    │  • Refresh quotidien après clôture (18h CET)
    │
    ▼
[4] CONVERSION DEVISES
    │  • Taux ECB quotidiens (XML feed)
    │  • Toutes les valeurs converties en EUR pour le dashboard
    │  • Stockage du taux au moment de chaque transaction
    │  • Graphes: option affichage EUR ou devise native
    │
    ▼
[5] MÉTADONNÉES INSTRUMENT
    │  • Secteur GICS, pays, devise, type
    │  • Finnhub Company Profile ou Yahoo Finance info
    │  • Cache: refresh hebdomadaire
    │
    ▼
[6] DIVIDENDES FUTURS
    │  • Finnhub dividend calendar
    │  • yfinance dividends history
    │  • Projection annuelle = dernier dividende × fréquence
```

#### Conversion Multi-Devises (détail)

```
┌─────────────────────────────────────────────────────────────┐
│ POSITIONS MULTI-DEVISES                                      │
│                                                              │
│  IBKR:  AAPL    150 × $230.50 = $34,575    → 32,013€       │
│  IBKR:  MSFT     50 × $420.00 = $21,000    → 19,444€       │
│  TR:    VWCE     80 × €112.30 =  €8,984    →  8,984€       │
│  Bourso: BNP    200 ×  €62.50 = €12,500    → 12,500€       │
│                                                              │
│  Taux EUR/USD: 1.0800 (ECB 2025-02-08)                      │
│  Taux EUR/GBP: 0.8600                                        │
│                                                              │
│  TOTAL PORTFOLIO: 72,941€                                    │
│  dont USD: $55,575 (52,457€)  — 71.9%                       │
│  dont EUR: €21,484            — 28.1%                        │
└─────────────────────────────────────────────────────────────┘
```

**Règles de conversion :**
- Patrimoine global toujours affiché en **EUR** (devise de référence)
- Chaque position affiche aussi sa valeur en **devise native**
- Les P&L sont calculés en devise native puis convertis
- L'impact devise est montré séparément : P&L devise vs P&L sous-jacent
- Taux de change historiques stockés pour recalculer les graphes passés

### 2.8 Graphiques Synthétiques

#### Dashboard Principal (Net Worth)

| Graphique | Type | Données | Périodes |
|---|---|---|---|
| **Évolution patrimoine** | Area chart empilé | Net worth total avec décomposition par classe | 1M, 3M, 6M, YTD, 1A, 3A, MAX |
| **Répartition actifs** | Donut chart | % par classe d'actif | Snapshot actuel |
| **Répartition établissements** | Horizontal bar | € par institution | Snapshot actuel |
| **Variation patrimoine** | KPI cards | Δ jour, semaine, mois, YTD en € et % | Temps réel |

#### Portfolio

| Graphique | Type | Données | Détail |
|---|---|---|---|
| **Performance cumulée** | Line chart multi-séries | Mon portfolio vs S&P500 vs MSCI World vs CAC40 | Base 100 à la date de début |
| **Allocation sectorielle** | Treemap ou donut | % par secteur GICS | Drill-down par position |
| **Allocation géographique** | World map ou donut | % par pays/zone | US, Europe, EM, Asia |
| **Allocation par devise** | Donut | % EUR, USD, GBP, autre | Exposition FX |
| **Top positions** | Horizontal bar | Top 10 par poids | Avec P&L coloré |
| **Cours + achats** | Candlestick / line | Historique cours + markers achats/ventes | Par position |
| **P&L par position** | Heatmap ou bar | P&L en € et % | Vert/Rouge |

#### Dividendes

| Graphique | Type | Données |
|---|---|---|
| **Calendrier dividendes** | Timeline / calendar | Prochains paiements avec montants estimés |
| **Dividendes mensuels** | Bar chart | Montant reçu par mois (12 derniers mois) |
| **Dividendes annuels** | Bar chart | Montant reçu par année |
| **Rendement par position** | Table triée | Yield % × montant annuel estimé |

#### Budget

| Graphique | Type | Données |
|---|---|---|
| **Revenus vs Dépenses** | Bar chart empilé | Par mois, 12 derniers mois |
| **Taux d'épargne** | Line chart + KPI | % épargne mensuel avec tendance |
| **Top catégories** | Donut + bar | Top 10 catégories de dépenses |
| **Cashflow cumulé** | Area chart | Cumul entrées - sorties dans le mois |

### 2.9 Analyses Avancées

- **Score de diversification** (0-100) :
  - Basé sur : nombre de classes d'actifs, répartition géographique, secteurs, devises
  - Pénalité si >50% dans un seul actif, secteur ou pays
  - Comparaison avec portfolio "idéal" (60/40, All-World, etc.)
- **Détection de frais cachés** :
  - TER (Total Expense Ratio) des ETF/fonds
  - Frais de gestion AV (Boursobank)
  - Impact annuel estimé en €
- **Projection patrimoine** (simulateur) :
  - Inputs : épargne mensuelle, rendement attendu, inflation, durée
  - Output : graphe projection net worth sur 10/20/30 ans
  - Scénarios : optimiste, réaliste, pessimiste
- **Rapport hebdomadaire** (généré automatiquement) :
  - Performance semaine (€ et %)
  - Dividendes reçus
  - Alertes (baisse >5%, position concentrée, etc.)
- **Alertes prix** :
  - Seuils haut/bas par position
  - Notification push quand seuil franchi

## 3. Modèle de Données

### Tables principales

```sql
-- Établissements connectés
CREATE TABLE institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,              -- 'ibkr', 'trade_republic', 'boursobank', 'credit_agricole'
    display_name TEXT NOT NULL,
    scraper_type TEXT NOT NULL,      -- 'api', 'playwright', 'websocket'
    credentials_encrypted BYTEA,     -- AES-256 encrypted
    last_sync_at TIMESTAMPTZ,
    sync_status TEXT DEFAULT 'idle', -- 'idle', 'syncing', 'error', 'otp_required'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Comptes (CC, livret, PEA, CTO, AV...)
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID REFERENCES institutions(id),
    external_id TEXT,                -- ID chez l'établissement
    name TEXT NOT NULL,
    account_type TEXT NOT NULL,      -- 'checking', 'savings', 'pea', 'cto', 'av', 'loan'
    currency TEXT DEFAULT 'EUR',
    balance DECIMAL(15,2) NOT NULL DEFAULT 0,
    is_pro BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transactions bancaires
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES accounts(id),
    external_id TEXT,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    category TEXT,                   -- auto-catégorisé
    category_manual TEXT,            -- override utilisateur
    merchant TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tx_account_date ON transactions(account_id, date DESC);

-- Positions (actions, ETF, crypto...)
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES accounts(id),
    ticker TEXT NOT NULL,
    isin TEXT,
    name TEXT NOT NULL,
    quantity DECIMAL(15,6) NOT NULL,
    avg_cost DECIMAL(15,4),          -- PRU
    current_price DECIMAL(15,4),
    currency TEXT DEFAULT 'EUR',
    asset_type TEXT NOT NULL,        -- 'stock', 'etf', 'bond', 'crypto', 'fund'
    sector TEXT,                     -- GICS sector
    country TEXT,                    -- ISO 3166
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_pos_account ON positions(account_id);

-- Historique positions (snapshots quotidiens)
CREATE TABLE position_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES positions(id),
    date DATE NOT NULL,
    quantity DECIMAL(15,6),
    price DECIMAL(15,4),
    value DECIMAL(15,2),
    UNIQUE(position_id, date)
);

-- Dividendes
CREATE TABLE dividends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES positions(id),
    ex_date DATE,
    pay_date DATE,
    amount_per_share DECIMAL(10,6),
    total_amount DECIMAL(15,2),
    currency TEXT DEFAULT 'EUR'
);

-- Patrimoine quotidien (snapshot net worth)
CREATE TABLE networth_history (
    date DATE PRIMARY KEY,
    total_assets DECIMAL(15,2),
    total_liabilities DECIMAL(15,2),
    net_worth DECIMAL(15,2),
    breakdown JSONB                  -- { "cash": 1000, "stocks": 5000, ... }
);

-- Biens immobiliers
CREATE TABLE real_estate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address TEXT NOT NULL,
    city TEXT,
    postal_code TEXT,
    property_type TEXT,              -- 'primary', 'rental', 'secondary'
    surface_m2 DECIMAL(8,2),
    purchase_price DECIMAL(15,2),
    purchase_date DATE,
    estimated_value DECIMAL(15,2),
    loan_remaining DECIMAL(15,2),
    monthly_rent DECIMAL(10,2),      -- si locatif
    monthly_payment DECIMAL(10,2),   -- mensualité crédit
    loan_rate DECIMAL(5,3),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Syncs log
CREATE TABLE sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID REFERENCES institutions(id),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,            -- 'success', 'error', 'otp_required'
    accounts_synced INT DEFAULT 0,
    transactions_added INT DEFAULT 0,
    error_message TEXT
);

-- Cours historiques (daily OHLCV)
CREATE TABLE price_history (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4) NOT NULL,
    volume BIGINT,
    currency TEXT DEFAULT 'EUR',
    PRIMARY KEY (ticker, date)
);

-- Mapping ISIN ↔ Ticker
CREATE TABLE isin_ticker_map (
    isin TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    name TEXT,
    exchange TEXT,              -- 'XETR', 'XPAR', 'XNAS', 'XNYS'
    currency TEXT DEFAULT 'EUR',
    asset_type TEXT,            -- 'stock', 'etf', 'bond', 'fund'
    sector TEXT,                -- GICS sector
    country TEXT,               -- ISO 3166
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ticker ON isin_ticker_map(ticker);

-- Taux de change historiques
CREATE TABLE exchange_rates (
    date DATE NOT NULL,
    base_currency TEXT DEFAULT 'EUR',
    quote_currency TEXT NOT NULL,   -- 'USD', 'GBP', 'CHF', etc.
    rate DECIMAL(12,6) NOT NULL,    -- 1 EUR = X quote_currency
    PRIMARY KEY (date, quote_currency)
);

-- Alertes prix
CREATE TABLE price_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL,
    alert_type TEXT NOT NULL,       -- 'above', 'below'
    threshold DECIMAL(15,4) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Règles de catégorisation
CREATE TABLE category_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern TEXT NOT NULL,           -- regex
    category TEXT NOT NULL,
    priority INT DEFAULT 0,
    is_user_defined BOOLEAN DEFAULT FALSE
);
```

## 4. API Endpoints (Rust/Axum)

```
GET  /api/v1/networth                      Patrimoine global + historique
GET  /api/v1/networth/breakdown            Répartition par classe/établissement

GET  /api/v1/accounts                      Liste tous les comptes
GET  /api/v1/accounts/:id                  Détail compte + solde
GET  /api/v1/accounts/:id/transactions     Transactions paginées

GET  /api/v1/portfolio                     Vue consolidée positions
GET  /api/v1/portfolio/performance         TWR, MWR, benchmark
GET  /api/v1/portfolio/allocation          Répartition secteur/geo/devise
GET  /api/v1/portfolio/dividends           Calendrier + historique dividendes
GET  /api/v1/positions/:id                 Détail position + historique cours

GET  /api/v1/budget/monthly                Revenus/dépenses par mois
GET  /api/v1/budget/categories             Top catégories
GET  /api/v1/budget/recurring              Récurrences détectées

GET  /api/v1/real-estate                   Liste biens immobiliers
POST /api/v1/real-estate                   Ajouter un bien
PUT  /api/v1/real-estate/:id               Modifier un bien

POST /api/v1/sync                          Sync manuelle globale
POST /api/v1/sync/:institution             Sync un établissement
GET  /api/v1/sync/status                   Status de toutes les syncs
GET  /api/v1/sync/logs                     Historique des syncs

PUT  /api/v1/transactions/:id/category     Re-catégoriser une transaction

GET  /api/v1/market/quote/:ticker          Cours actuel (cache 5min)
GET  /api/v1/market/history/:ticker        Historique OHLCV (params: from, to, interval)
GET  /api/v1/market/search?q=              Recherche ticker/ISIN/nom
GET  /api/v1/market/fx                     Taux de change actuels EUR/X

GET  /api/v1/analytics/diversification     Score diversification + détails
GET  /api/v1/analytics/fees                Frais cachés détectés
GET  /api/v1/analytics/projection          Simulation patrimoine (params: monthly_savings, return, years)
GET  /api/v1/analytics/weekly-report       Rapport hebdomadaire

GET  /api/v1/alerts                        Liste alertes prix
POST /api/v1/alerts                        Créer alerte
DELETE /api/v1/alerts/:id                  Supprimer alerte
```

## 5. Scrapers

### 5.1 IBKR (Client Portal API)

- **Méthode** : REST API officielle (Client Portal Gateway)
- **Auth** : OAuth / session token
- **Données** : positions, transactions, soldes, P&L
- **Doc** : https://www.interactivebrokers.com/api/doc.html

### 5.2 Trade Republic

- **Méthode** : Playwright (app.traderepublic.com) ou reverse WS
- **Auth** : phone number + PIN + OTP SMS
- **Données** : positions, transactions, dividendes, savings plans
- **Attention** : anti-bot strict, throttling nécessaire

### 5.3 Boursobank

- **Méthode** : Playwright (clients.boursobank.com)
- **Auth** : identifiant + mot de passe + clavier virtuel
- **Données** : CC, livrets, AV, PEA, CTO
- **Attention** : clavier virtuel randomisé (capture positions boutons)

### 5.4 Crédit Agricole

- **Méthode** : Playwright (www.credit-agricole.fr)
- **Auth** : numéro compte + code PIN (clavier virtuel)
- **Données** : CC perso, CC pro, livrets, crédits
- **Attention** : 2 espaces distincts (perso + pro), SCA occasionnel

### 5.5 Market Data Providers

#### Yahoo Finance (yfinance) — Source principale

```python
import yfinance as yf

# Cours actuel
ticker = yf.Ticker("AAPL")
info = ticker.info  # prix, nom, secteur, pays, devise, market_cap...
price = info["currentPrice"]

# Historique daily
hist = ticker.history(period="5y")  # OHLCV DataFrame

# Dividendes
divs = ticker.dividends  # historique
next_div = ticker.calendar  # prochaine date

# Recherche par ISIN → ticker
# yfinance ne supporte pas ISIN nativement
# Stratégie: table locale isin_ticker_map + Yahoo Finance search fallback
```

#### ECB FX Rates — Taux de change

```python
import httpx
from xml.etree import ElementTree

ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_HIST = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"

async def fetch_ecb_rates() -> dict[str, Decimal]:
    """Taux EUR → X (daily, ~16h CET)."""
    r = await httpx.AsyncClient().get(ECB_DAILY)
    root = ElementTree.fromstring(r.text)
    ns = {"ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    rates = {}
    for cube in root.findall(".//ecb:Cube[@currency]", ns):
        rates[cube.get("currency")] = Decimal(cube.get("rate"))
    return rates  # {"USD": Decimal("1.0800"), "GBP": Decimal("0.8600"), ...}
```

#### Finnhub — Enrichissement

```python
import finnhub

client = finnhub.Client(api_key="free_key")

# Profil société (secteur, pays, etc.)
profile = client.company_profile2(symbol="AAPL")  # {sector, country, currency, ...}

# Dividendes à venir
divs = client.stock_dividends("AAPL", _from="2025-01-01", to="2025-12-31")

# Quote temps-réel (US uniquement en free tier)
quote = client.quote("AAPL")  # {c: current, h: high, l: low, o: open, pc: prev_close}
```

#### Scheduler Market Data

```
# CRON Market Data
# 
# Heures de marché EU (09:00-17:30 CET):
#   → Refresh cours toutes les 5 min
#
# Heures de marché US (15:30-22:00 CET):
#   → Refresh cours toutes les 5 min
#
# Hors marché:
#   → Refresh 1x après clôture (18h CET EU, 22:30 CET US)
#
# FX ECB:
#   → 1x/jour à 16:30 CET (publication ECB)
#
# Historique cours:
#   → 1x/jour à 23:00 CET (toutes les positions)
#
# Métadonnées instruments:
#   → 1x/semaine (secteur, pays, profil)
```

## 6. Sécurité

- Credentials bancaires chiffrés AES-256-GCM, clé dérivée d'un master password
- Master password jamais stocké (dérivé à chaque session via Argon2)
- API single-user, pas d'auth HTTP (réseau local uniquement) OU token JWT
- Pas de données en clair dans les logs
- Scrapers : headless, pas de screenshots persistants

## 7. Contraintes Techniques

- **Précision** : DECIMAL(15,2) pour les montants, DECIMAL(15,6) pour les quantités
- **Devises** : Support multi-devises (EUR, USD, GBP), conversion via ECB rates
- **Timezone** : Tout en UTC, conversion côté client
- **Pagination** : Cursor-based pour transactions (potentiellement des milliers)
- **Cache** : Redis pour les données fréquemment accédées (net worth, positions)
