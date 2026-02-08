---
name: bank-scraper
description: Bank and broker scraping with Playwright and APIs. Use when building or modifying scrapers for IBKR, Trade Republic, Boursobank, or Crédit Agricole. Handles login flows, virtual keyboards, OTP, anti-bot evasion, and financial data extraction (balances, positions, transactions, dividends).
---

# Bank Scraper

Scraping de données bancaires et brokerage via Playwright headless et APIs.

## Architecture Scraper

Chaque scraper implémente l'interface `BaseScraper` :

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from datetime import date

@dataclass
class Account:
    external_id: str
    name: str
    account_type: str       # 'checking', 'savings', 'pea', 'cto', 'av', 'loan'
    balance: Decimal
    currency: str = 'EUR'
    is_pro: bool = False

@dataclass
class Position:
    ticker: str
    isin: str | None
    name: str
    quantity: Decimal
    avg_cost: Decimal | None
    current_price: Decimal
    currency: str = 'EUR'
    asset_type: str = 'stock'

@dataclass
class Transaction:
    external_id: str
    date: date
    description: str
    amount: Decimal
    category: str | None = None

class BaseScraper(ABC):
    @abstractmethod
    async def login(self) -> bool: ...
    
    @abstractmethod
    async def get_accounts(self) -> list[Account]: ...
    
    @abstractmethod
    async def get_positions(self, account_id: str) -> list[Position]: ...
    
    @abstractmethod
    async def get_transactions(self, account_id: str, since: date) -> list[Transaction]: ...
    
    async def sync_all(self) -> dict:
        """Full sync: login → accounts → positions → transactions"""
        if not await self.login():
            raise AuthError("Login failed")
        accounts = await self.get_accounts()
        for acc in accounts:
            acc.positions = await self.get_positions(acc.external_id)
            acc.transactions = await self.get_transactions(acc.external_id, since=date.today() - timedelta(days=90))
        return {"accounts": accounts}
```

## Patterns par Établissement

### IBKR — Client Portal API (pas Playwright)

```python
# IBKR utilise son API REST officielle, PAS de scraping
# Doc: https://www.interactivebrokers.com/api/doc.html
import httpx

class IBKRScraper(BaseScraper):
    BASE = "https://localhost:5000/v1/api"  # Client Portal Gateway local
    
    async def login(self):
        # Le gateway gère l'auth via navigateur
        r = await self.client.get(f"{self.BASE}/iserver/auth/status")
        return r.json().get("authenticated", False)
    
    async def get_accounts(self):
        r = await self.client.get(f"{self.BASE}/portfolio/accounts")
        # ...
    
    async def get_positions(self, account_id):
        r = await self.client.get(f"{self.BASE}/portfolio/{account_id}/positions/0")
        # ...
```

### Boursobank — Clavier Virtuel

```python
# Le clavier virtuel randomise les positions des chiffres
# Stratégie : lire les data-attributes ou positions CSS des boutons

async def solve_virtual_keyboard(page, pin: str):
    """Résoud le clavier virtuel Boursobank."""
    for digit in pin:
        # Chaque bouton a un data-key ou aria-label avec le chiffre
        btn = page.locator(f'button[data-key="{digit}"]')
        if await btn.count() == 0:
            # Fallback: chercher par le texte visible
            btn = page.locator(f'button:has-text("{digit}")').first
        await btn.click()
        await page.wait_for_timeout(random.randint(100, 300))
```

### Crédit Agricole — Deux Espaces

```python
# CA a des espaces distincts perso/pro avec le même login
# Naviguer entre les deux après authentification

async def switch_space(page, space: str):
    """Switch entre espace perso et pro."""
    if space == "pro":
        await page.click('[data-testid="switch-pro"]')  # ou lien "Espace pro"
    await page.wait_for_load_state("networkidle")
```

## Anti-Bot & Robustesse

```python
# OBLIGATOIRE pour tous les scrapers Playwright

# 1. User-agent réaliste
context = await browser.new_context(
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    viewport={"width": 1280, "height": 720},
    locale="fr-FR",
    timezone_id="Europe/Paris",
)

# 2. Délais humains entre actions
async def human_delay():
    await asyncio.sleep(random.uniform(0.5, 2.0))

# 3. Retry avec backoff
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=60))
async def safe_sync(scraper):
    return await scraper.sync_all()

# 4. Pas de parallélisme entre établissements (un à la fois)
# 5. Screenshots uniquement en mode debug (jamais persistés en prod)
```

## Gestion OTP

```python
# Deux stratégies pour l'OTP :

# 1. TOTP automatique (si l'établissement le supporte)
import pyotp
totp = pyotp.TOTP(secret)
code = totp.now()

# 2. OTP SMS — notification + attente input
async def wait_for_otp(institution: str, timeout: int = 300):
    """Attend que l'utilisateur saisisse l'OTP via l'API."""
    # POST /api/v1/sync/{institution}/otp avec le code
    # Le scraper attend en polling la réponse
    ...
```

## Scheduler

```python
# CRON 4x/jour : 06:00, 12:00, 18:00, 00:00 UTC
# Ordre : IBKR (API rapide) → TR → Boursobank → CA
# Un seul scraper à la fois (pas de parallélisme)
# Snapshot net worth après chaque sync complète
```
