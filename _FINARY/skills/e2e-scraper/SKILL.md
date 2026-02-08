---
name: e2e-scraper
description: End-to-end testing for bank scrapers. Use when writing or modifying tests for the scraping layer. Covers mocking bank websites, testing virtual keyboard solvers, OTP flows, data extraction validation, and scraper resilience (retry, error handling, anti-bot detection).
---

# E2E Scraper Testing

Tests end-to-end pour les scrapers bancaires. Validation des flows de login, extraction de données, et gestion d'erreurs.

## Stratégie de Test

Les scrapers bancaires ne peuvent PAS être testés contre les vrais sites en CI. Stratégie :

1. **Mock HTML** : Pages HTML statiques simulant chaque banque
2. **Playwright fixtures** : Intercepter les requêtes réseau
3. **Data validation** : Vérifier le parsing des données extraites

## Mock Server Pattern

```python
import pytest
from playwright.async_api import async_playwright
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

@pytest.fixture
def mock_bank_server():
    """Serveur local avec pages HTML mockées."""
    handler = SimpleHTTPRequestHandler
    handler.directory = "tests/fixtures/html"
    server = HTTPServer(("localhost", 9999), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield "http://localhost:9999"
    server.shutdown()
```

## Fixtures HTML

```
tests/fixtures/html/
├── boursobank/
│   ├── login.html          # Page login avec clavier virtuel
│   ├── accounts.html       # Liste comptes
│   ├── transactions.html   # Historique transactions
│   └── portfolio.html      # Positions bourse
├── credit_agricole/
│   ├── login.html          # Login avec PIN pad
│   ├── accounts_perso.html
│   ├── accounts_pro.html
│   └── transactions.html
└── trade_republic/
    ├── login.html
    ├── portfolio.html
    └── timeline.html
```

## Tests Pattern

```python
import pytest
from decimal import Decimal

class TestBoursobankScraper:
    """Tests pour le scraper Boursobank."""

    async def test_login_virtual_keyboard(self, mock_bank_server, page):
        """Le scraper résout le clavier virtuel correctement."""
        await page.goto(f"{mock_bank_server}/boursobank/login.html")
        scraper = BoursobankScraper(page, credentials=TEST_CREDS)
        result = await scraper.login()
        assert result is True

    async def test_extract_accounts(self, mock_bank_server, page):
        """Extraction correcte des comptes et soldes."""
        await page.goto(f"{mock_bank_server}/boursobank/accounts.html")
        scraper = BoursobankScraper(page, credentials=TEST_CREDS)
        accounts = await scraper.get_accounts()
        
        assert len(accounts) >= 1
        for acc in accounts:
            assert acc.name
            assert acc.account_type in ('checking', 'savings', 'pea', 'cto', 'av')
            assert isinstance(acc.balance, Decimal)
            assert acc.currency == 'EUR'

    async def test_extract_transactions(self, mock_bank_server, page):
        """Transactions parsées avec montant et description."""
        # ...
        for tx in transactions:
            assert tx.date
            assert tx.description
            assert isinstance(tx.amount, Decimal)

    async def test_login_failure_handled(self, mock_bank_server, page):
        """Login échoué retourne False, pas d'exception."""
        scraper = BoursobankScraper(page, credentials=WRONG_CREDS)
        result = await scraper.login()
        assert result is False

    async def test_otp_required_detected(self, mock_bank_server, page):
        """Détection correcte de la demande OTP."""
        # La page mock affiche un formulaire OTP
        # Le scraper doit lever OTPRequired, pas crasher
```

## Data Validation

```python
def validate_account(account: Account):
    """Validation stricte des données extraites."""
    assert account.external_id, "external_id requis"
    assert account.name, "name requis"
    assert account.account_type in VALID_ACCOUNT_TYPES
    assert account.currency in ('EUR', 'USD', 'GBP')
    assert account.balance is not None

def validate_position(position: Position):
    assert position.ticker or position.isin, "ticker ou isin requis"
    assert position.name, "name requis"
    assert position.quantity > 0, "quantity > 0"
    assert position.current_price >= 0, "price >= 0"

def validate_transaction(tx: Transaction):
    assert tx.date, "date requise"
    assert tx.description, "description requise"
    assert tx.amount != 0, "amount != 0"
```
