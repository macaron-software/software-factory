"""Boursobank scraper using Playwright.

Handles the randomized virtual keyboard for login.
Extracts: checking, savings, life insurance, PEA, CTO accounts.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from scrapers.base import BaseScraper, OTPRequiredError
from scrapers.models import Account, AccountType, AssetType, Position, Transaction

# Playwright imported lazily to allow testing without browser
_pw = None


def _get_playwright():
    global _pw
    if _pw is None:
        from playwright.async_api import async_playwright
        _pw = async_playwright
    return _pw


class BoursobankScraper(BaseScraper):
    institution_name = "boursobank"
    display_name = "Boursobank"
    scraper_type = "playwright"

    LOGIN_URL = "https://clients.boursobank.com/connexion/"

    def __init__(self, username: str = "", password: str = "") -> None:
        super().__init__()
        self.username = username
        self.password = password
        self._pw_context = None
        self._browser = None
        self._page = None

    async def login(self) -> None:
        pw = _get_playwright()
        self._pw_context = await pw().__aenter__()
        self._browser = await self._pw_context.chromium.launch(headless=True)
        ctx = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        self._page = await ctx.new_page()

        await self._page.goto(self.LOGIN_URL, wait_until="networkidle")

        # Enter username
        await self._page.fill('input[name="login"]', self.username)

        # Virtual keyboard: map digit to button position via data-attribute
        for digit in self.password:
            btn = await self._page.query_selector(f'button[data-matrix-key="{digit}"]')
            if btn is None:
                # Fallback: find button by visible text
                btn = await self._page.query_selector(f'button:has-text("{digit}")')
            if btn:
                await btn.click()
                await self._page.wait_for_timeout(100)

        await self._page.click('button[type="submit"]')
        await self._page.wait_for_load_state("networkidle")

        # Check for OTP
        if await self._page.query_selector('[data-testid="otp-input"]'):
            raise OTPRequiredError("sms")

        self.logger.info("Boursobank login successful")

    async def logout(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw_context:
            await self._pw_context.__aexit__(None, None, None)

    async def fetch_accounts(self) -> list[Account]:
        """Scrape accounts from dashboard page."""
        assert self._page is not None
        await self._page.goto(
            "https://clients.boursobank.com/dashboard", wait_until="networkidle"
        )

        accounts = []
        inst_id = uuid.uuid5(uuid.NAMESPACE_DNS, "boursobank")

        # Parse account rows from the dashboard
        rows = await self._page.query_selector_all('[data-testid="account-row"]')
        for row in rows:
            name_el = await row.query_selector('[data-testid="account-name"]')
            balance_el = await row.query_selector('[data-testid="account-balance"]')
            type_el = await row.query_selector('[data-testid="account-type"]')

            name = await name_el.inner_text() if name_el else "Compte Boursobank"
            balance_text = await balance_el.inner_text() if balance_el else "0"
            type_text = await type_el.inner_text() if type_el else ""

            balance = _parse_amount(balance_text)
            account_type = _detect_account_type(type_text, name)

            accounts.append(
                Account(
                    institution_id=inst_id,
                    name=name,
                    account_type=account_type,
                    currency="EUR",
                    balance=balance,
                )
            )

        return accounts

    async def fetch_transactions(self, account: Account) -> list[Transaction]:
        """Scrape transactions for a given account."""
        assert self._page is not None
        # Navigate to account transactions page
        # URL pattern: /compte/cav/{external_id}/mouvements
        if not account.external_id:
            return []

        await self._page.goto(
            f"https://clients.boursobank.com/compte/cav/{account.external_id}/mouvements",
            wait_until="networkidle",
        )

        transactions = []
        rows = await self._page.query_selector_all('[data-testid="transaction-row"]')
        for row in rows:
            date_el = await row.query_selector('[data-testid="tx-date"]')
            desc_el = await row.query_selector('[data-testid="tx-description"]')
            amount_el = await row.query_selector('[data-testid="tx-amount"]')

            tx_date_text = await date_el.inner_text() if date_el else ""
            description = await desc_el.inner_text() if desc_el else ""
            amount_text = await amount_el.inner_text() if amount_el else "0"

            transactions.append(
                Transaction(
                    account_id=account.id,
                    date=_parse_date(tx_date_text),
                    description=description.strip(),
                    amount=_parse_amount(amount_text),
                )
            )

        return transactions

    async def fetch_positions(self, account: Account) -> list[Position]:
        """Scrape positions for PEA/CTO/AV accounts."""
        if account.account_type not in (AccountType.PEA, AccountType.CTO, AccountType.AV):
            return []
        assert self._page is not None

        await self._page.goto(
            f"https://clients.boursobank.com/bourse/portefeuille/{account.external_id}",
            wait_until="networkidle",
        )

        positions = []
        rows = await self._page.query_selector_all('[data-testid="position-row"]')
        for row in rows:
            name_el = await row.query_selector('[data-testid="pos-name"]')
            isin_el = await row.query_selector('[data-testid="pos-isin"]')
            qty_el = await row.query_selector('[data-testid="pos-quantity"]')
            price_el = await row.query_selector('[data-testid="pos-price"]')
            cost_el = await row.query_selector('[data-testid="pos-avg-cost"]')

            name = await name_el.inner_text() if name_el else ""
            isin = await isin_el.inner_text() if isin_el else None
            quantity = _parse_amount(await qty_el.inner_text()) if qty_el else Decimal("0")
            price = _parse_amount(await price_el.inner_text()) if price_el else Decimal("0")
            cost = _parse_amount(await cost_el.inner_text()) if cost_el else None

            positions.append(
                Position(
                    account_id=account.id,
                    ticker=isin or name[:10],
                    isin=isin,
                    name=name,
                    quantity=quantity,
                    avg_cost=cost,
                    current_price=price,
                    currency="EUR",
                    asset_type=AssetType.ETF if "ETF" in name.upper() else AssetType.STOCK,
                )
            )

        return positions


def _parse_amount(text: str) -> Decimal:
    """Parse French-formatted amount: '1 234,56 €' → Decimal('1234.56')."""
    cleaned = text.replace("€", "").replace("\u202f", "").replace("\xa0", "").replace(" ", "").strip()
    cleaned = cleaned.replace(",", ".")
    # Handle negative with dash or minus
    cleaned = cleaned.replace("−", "-").replace("–", "-")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def _parse_date(text: str) -> date:
    """Parse French date: '08/02/2025' → date(2025, 2, 8)."""
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date.today()


def _detect_account_type(type_text: str, name: str) -> AccountType:
    """Detect account type from Boursobank labels."""
    combined = (type_text + " " + name).upper()
    if "PEA" in combined:
        return AccountType.PEA
    if "CTO" in combined or "TITRE" in combined:
        return AccountType.CTO
    if "VIE" in combined or "AV " in combined:
        return AccountType.AV
    if "LIVRET" in combined or "LDD" in combined or "LEP" in combined:
        return AccountType.SAVINGS
    if "PRET" in combined or "PRÊT" in combined.upper() or "CREDIT" in combined or "CRÉDIT" in combined.upper():
        return AccountType.LOAN
    return AccountType.CHECKING
