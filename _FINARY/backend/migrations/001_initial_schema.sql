-- 001_initial_schema.sql
-- Full schema for Finary patrimoine tracker

BEGIN;

-- Établissements connectés
CREATE TABLE IF NOT EXISTS institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    scraper_type TEXT NOT NULL,
    credentials_encrypted BYTEA,
    last_sync_at TIMESTAMPTZ,
    sync_status TEXT DEFAULT 'idle',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Comptes
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
    external_id TEXT,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    currency TEXT DEFAULT 'EUR',
    balance DECIMAL(15,2) NOT NULL DEFAULT 0,
    is_pro BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transactions bancaires
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    external_id TEXT,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    category TEXT,
    category_manual TEXT,
    merchant TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tx_account_date ON transactions(account_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);

-- Positions investissement
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    isin TEXT,
    name TEXT NOT NULL,
    quantity DECIMAL(15,6) NOT NULL,
    avg_cost DECIMAL(15,4),
    current_price DECIMAL(15,4),
    currency TEXT DEFAULT 'EUR',
    asset_type TEXT NOT NULL,
    sector TEXT,
    country TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pos_account ON positions(account_id);
CREATE INDEX IF NOT EXISTS idx_pos_ticker ON positions(ticker);

-- Historique positions (snapshots)
CREATE TABLE IF NOT EXISTS position_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES positions(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    quantity DECIMAL(15,6),
    price DECIMAL(15,4),
    value DECIMAL(15,2),
    UNIQUE(position_id, date)
);

-- Dividendes
CREATE TABLE IF NOT EXISTS dividends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES positions(id) ON DELETE CASCADE,
    ex_date DATE,
    pay_date DATE,
    amount_per_share DECIMAL(10,6),
    total_amount DECIMAL(15,2),
    currency TEXT DEFAULT 'EUR'
);

-- Net worth quotidien
CREATE TABLE IF NOT EXISTS networth_history (
    date DATE PRIMARY KEY,
    total_assets DECIMAL(15,2),
    total_liabilities DECIMAL(15,2),
    net_worth DECIMAL(15,2),
    breakdown JSONB
);

-- Biens immobiliers
CREATE TABLE IF NOT EXISTS real_estate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address TEXT NOT NULL,
    city TEXT,
    postal_code TEXT,
    property_type TEXT,
    surface_m2 DECIMAL(8,2),
    purchase_price DECIMAL(15,2),
    purchase_date DATE,
    estimated_value DECIMAL(15,2),
    loan_remaining DECIMAL(15,2),
    monthly_rent DECIMAL(10,2),
    monthly_payment DECIMAL(10,2),
    loan_rate DECIMAL(5,3),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sync logs
CREATE TABLE IF NOT EXISTS sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    accounts_synced INT DEFAULT 0,
    transactions_added INT DEFAULT 0,
    error_message TEXT
);

-- Cours historiques
CREATE TABLE IF NOT EXISTS price_history (
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

-- ISIN ↔ Ticker mapping
CREATE TABLE IF NOT EXISTS isin_ticker_map (
    isin TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    name TEXT,
    exchange TEXT,
    currency TEXT DEFAULT 'EUR',
    asset_type TEXT,
    sector TEXT,
    country TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_isin_ticker ON isin_ticker_map(ticker);

-- Taux de change
CREATE TABLE IF NOT EXISTS exchange_rates (
    date DATE NOT NULL,
    base_currency TEXT DEFAULT 'EUR',
    quote_currency TEXT NOT NULL,
    rate DECIMAL(12,6) NOT NULL,
    PRIMARY KEY (date, quote_currency)
);

-- Alertes prix
CREATE TABLE IF NOT EXISTS price_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    threshold DECIMAL(15,4) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Règles de catégorisation
CREATE TABLE IF NOT EXISTS category_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern TEXT NOT NULL,
    category TEXT NOT NULL,
    priority INT DEFAULT 0,
    is_user_defined BOOLEAN DEFAULT FALSE
);

-- Seed default category rules
INSERT INTO category_rules (pattern, category, priority) VALUES
    ('CARREFOUR|LECLERC|AUCHAN|LIDL|MONOPRIX|FRANPRIX|PICARD|CASINO|INTERMARCHE', 'alimentation', 10),
    ('UBER EATS|DELIVEROO|JUST EAT|DOMINOS|MCDONALDS|BURGER KING|KFC|STARBUCKS', 'restauration', 10),
    ('SNCF|RATP|UBER |BOLT|LIME|BLABLACAR|TOTAL ENERGIES|SHELL|BP |ESSO', 'transport', 10),
    ('NETFLIX|SPOTIFY|DISNEY|CANAL|AMAZON PRIME|APPLE\.COM|DEEZER|OCS|YOUTUBE', 'abonnements', 10),
    ('SFR|ORANGE|FREE |BOUYGUES', 'telecom', 10),
    ('LOYER|RENT|FONCIA|NEXITY|ORPI|CENTURY 21', 'logement', 10),
    ('EDF|ENGIE|VEOLIA|SUEZ|GAZ', 'energie', 10),
    ('AXA|MAIF|MACIF|MATMUT|ALLIANZ|GENERALI|MMA|GROUPAMA', 'assurance', 10),
    ('PHARMACIE|DOCTOLIB|AMELI|CPAM|MUTUELLE', 'sante', 10),
    ('FNAC|DARTY|AMAZON|CDISCOUNT|ZALANDO|ZARA|H&M|DECATHLON|IKEA|LEROY MERLIN', 'shopping', 10),
    ('SALAIRE|PAIE|VIR.*EMPL|TRAITEMENT', 'revenus', 20),
    ('ALLOC|CAF|POLE EMPLOI|FRANCE TRAVAIL', 'aides', 15),
    ('IMPOTS|TRESOR PUBLIC|DGFIP', 'impots', 15),
    ('VIREMENT.*EPARGNE|VIR.*LIVRET|VIR.*PEA', 'epargne', 5)
ON CONFLICT DO NOTHING;

COMMIT;
