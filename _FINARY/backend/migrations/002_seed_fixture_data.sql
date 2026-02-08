-- 002_seed_fixture_data.sql
-- Fixture data matching scrapers/tests/fixtures/sample_portfolio.json

BEGIN;

-- Institutions
INSERT INTO institutions (id, name, display_name, scraper_type) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'ibkr', 'Interactive Brokers', 'api'),
    ('a1000000-0000-0000-0000-000000000002', 'trade_republic', 'Trade Republic', 'playwright'),
    ('a1000000-0000-0000-0000-000000000003', 'boursobank', 'Boursobank', 'playwright'),
    ('a1000000-0000-0000-0000-000000000004', 'credit_agricole', 'Crédit Agricole', 'playwright')
ON CONFLICT (name) DO NOTHING;

-- Accounts
INSERT INTO accounts (id, institution_id, name, account_type, currency, balance, is_pro) VALUES
    ('b1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'IBKR Brokerage USD', 'cto', 'USD', 87543.21, false),
    ('b1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000002', 'Trade Republic CTO', 'cto', 'EUR', 23456.78, false),
    ('b1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000002', 'Trade Republic Cash', 'checking', 'EUR', 1250.00, false),
    ('b1000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000003', 'Bourso Compte Courant', 'checking', 'EUR', 4532.15, false),
    ('b1000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000003', 'Bourso Livret A', 'savings', 'EUR', 22950.00, false),
    ('b1000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000003', 'Bourso PEA', 'pea', 'EUR', 45230.50, false),
    ('b1000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000003', 'Bourso Assurance Vie', 'av', 'EUR', 15000.00, false),
    ('b1000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000004', 'CA Compte Courant Perso', 'checking', 'EUR', 3210.45, false),
    ('b1000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000004', 'CA LDD', 'savings', 'EUR', 12000.00, false),
    ('b1000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000004', 'CA Compte Pro', 'checking', 'EUR', 18750.30, true),
    ('b1000000-0000-0000-0000-000000000011', 'a1000000-0000-0000-0000-000000000004', 'CA Prêt Immobilier', 'loan', 'EUR', -185000.00, false)
ON CONFLICT DO NOTHING;

-- Positions
INSERT INTO positions (id, account_id, ticker, isin, name, quantity, avg_cost, current_price, currency, asset_type, sector, country) VALUES
    ('c1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'AAPL', 'US0378331005', 'Apple Inc.', 150, 178.50, 230.50, 'USD', 'stock', 'Technology', 'US'),
    ('c1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000001', 'MSFT', 'US5949181045', 'Microsoft Corporation', 50, 380.00, 420.00, 'USD', 'stock', 'Technology', 'US'),
    ('c1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000001', 'VWCE.DE', 'IE00BK5BQT80', 'Vanguard FTSE All-World', 100, 95.20, 112.30, 'EUR', 'etf', null, null),
    ('c1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000002', 'IWDA.AS', 'IE00B4L5Y983', 'iShares Core MSCI World', 80, 72.50, 89.40, 'EUR', 'etf', null, null),
    ('c1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000002', 'SAP.DE', 'DE0007164600', 'SAP SE', 30, 145.00, 198.50, 'EUR', 'stock', 'Technology', 'DE'),
    ('c1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000006', 'BNP.PA', 'FR0000131104', 'BNP Paribas SA', 200, 52.30, 62.50, 'EUR', 'stock', 'Financials', 'FR'),
    ('c1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000006', 'CW8.PA', 'LU1681043599', 'Amundi MSCI World', 15, 380.00, 445.80, 'EUR', 'etf', null, null),
    ('c1000000-0000-0000-0000-000000000008', 'b1000000-0000-0000-0000-000000000006', 'AI.PA', 'FR0000120073', 'Air Liquide SA', 50, 155.00, 178.40, 'EUR', 'stock', 'Materials', 'FR')
ON CONFLICT DO NOTHING;

-- Transactions (sample)
INSERT INTO transactions (account_id, date, description, amount, category) VALUES
    ('b1000000-0000-0000-0000-000000000004', '2025-02-07', 'CARTE CARREFOUR CITY PARIS', -45.32, 'alimentation'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-06', 'CARTE UBER EATS', -28.50, 'restauration'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-05', 'VIR SALAIRE MACARON SOFTWARE SAS', 4500.00, 'revenus'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-05', 'PRLV NETFLIX', -13.49, 'abonnements'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-04', 'PRLV SPOTIFY PREMIUM', -10.99, 'abonnements'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-03', 'CARTE FNAC.COM', -89.99, 'shopping'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-03', 'PRLV FREE MOBILE', -19.99, 'telecom'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-01', 'PRLV LOYER FONCIA', -1250.00, 'logement'),
    ('b1000000-0000-0000-0000-000000000004', '2025-02-01', 'PRLV EDF', -75.00, 'energie'),
    ('b1000000-0000-0000-0000-000000000004', '2025-01-31', 'VIR EPARGNE VERS LIVRET A', -500.00, 'epargne'),
    ('b1000000-0000-0000-0000-000000000008', '2025-02-06', 'CARTE LECLERC DRIVE', -78.54, 'alimentation'),
    ('b1000000-0000-0000-0000-000000000008', '2025-02-04', 'CARTE PHARMACIE DU CENTRE', -23.80, 'sante'),
    ('b1000000-0000-0000-0000-000000000008', '2025-02-01', 'PRLV MACIF ASSURANCE AUTO', -65.00, 'assurance'),
    ('b1000000-0000-0000-0000-000000000008', '2025-02-01', 'ECHEANCE PRET IMMOBILIER', -1350.00, null),
    ('b1000000-0000-0000-0000-000000000010', '2025-02-05', 'VIR CLIENT PROJET WEB', 8500.00, 'revenus'),
    ('b1000000-0000-0000-0000-000000000010', '2025-02-03', 'PRLV URSSAF COTISATIONS', -2100.00, 'impots'),
    ('b1000000-0000-0000-0000-000000000010', '2025-02-01', 'CARTE OVH CLOUD', -45.60, null),
    ('b1000000-0000-0000-0000-000000000010', '2025-01-15', 'VIR CLIENT MISSION CONSEIL', 12000.00, 'revenus')
ON CONFLICT DO NOTHING;

-- Exchange rates
INSERT INTO exchange_rates (date, quote_currency, rate) VALUES
    ('2025-02-07', 'USD', 1.0380),
    ('2025-02-07', 'GBP', 0.8340),
    ('2025-02-07', 'CHF', 0.9420),
    ('2025-02-07', 'JPY', 157.80),
    ('2025-02-06', 'USD', 1.0395),
    ('2025-02-06', 'GBP', 0.8350),
    ('2025-02-06', 'CHF', 0.9415),
    ('2025-02-06', 'JPY', 158.10)
ON CONFLICT DO NOTHING;

-- Dividends
INSERT INTO dividends (position_id, ex_date, pay_date, amount_per_share, total_amount, currency) VALUES
    ('c1000000-0000-0000-0000-000000000001', '2025-02-07', '2025-02-15', 0.25, 37.50, 'USD'),
    ('c1000000-0000-0000-0000-000000000002', '2025-02-20', '2025-03-13', 0.83, 41.50, 'USD'),
    ('c1000000-0000-0000-0000-000000000006', '2025-05-22', '2025-05-27', 4.60, 920.00, 'EUR')
ON CONFLICT DO NOTHING;

-- Real estate
INSERT INTO real_estate (address, city, postal_code, property_type, surface_m2, purchase_price, purchase_date, estimated_value, loan_remaining, monthly_payment, loan_rate) VALUES
    ('15 rue de la Paix', 'Paris', '75002', 'primary', 65.0, 450000.00, '2022-06-15', 480000.00, 185000.00, 1350.00, 1.850)
ON CONFLICT DO NOTHING;

COMMIT;
