"""Crédit Agricole scraper using Playwright.

Handles: perso + pro spaces, virtual keyboard PIN login.
Regional URL pattern: www.credit-agricole.fr/ca-{region}/
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from scrapers.base import BaseScraper, OTPRequiredError
from scrapers.models import Account, AccountType, Transaction

_pw = None


def _get_playwright():
    global _pw
    if _pw is None:
        from playwright.async_api import async_playwright
        _pw = async_playwright
    return _pw


class CreditAgricoleScraper(BaseScraper):
    institution_name = "credit_agricole"
    display_name = "Crédit Agricole"
    scraper_type = "playwright"

    def __init__(
        self,
        region: str = "paris",
        account_number: str = "",
        pin: str = "",
        is_pro: bool = False,
    ) -> None:
        super().__init__()
        self.region = region
        self.account_number = account_number
        self.pin = pin
        self.is_pro = is_pro
        self._pw_context = None
        self._browser = None
        self._page = None

    @property
    def _base_url(self) -> str:
        prefix = "ca-" if not self.is_pro else "ca-"
        return f"https://www.credit-agricole.fr/{prefix}{self.region}"

    async def login(self) -> None:
        pw = _get_playwright()
        self._pw_context = await pw().__aenter__()
        self._browser = await self._pw_context.chromium.launch(headless=True)
        ctx = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        self._page = await ctx.new_page()

        space = "particulier" if not self.is_pro else "professionnel"
        await self._page.goto(
            f"{self._base_url}/{space}/acceder-a-mes-comptes.html",
            wait_until="networkidle",
        )

        # Enter account number
        await self._page.fill('#Login-account_number', self.account_number)

        # Virtual keyboard for PIN (6 digits)
        for digit in self.pin:
            btn = await self._page.query_selector(f'div.Login-keyboard button[data-value="{digit}"]')
            if btn:
                await btn.click()
                await self._page.wait_for_timeout(80)

        await self._page.click('#Login-submitButton')
        await self._page.wait_for_load_state("networkidle")

        # Check SCA / OTP
        sca_el = await self._page.query_selector('[data-testid="sca-challenge"]')
        if sca_el:
            raise OTPRequiredError("app_validation")

        self.logger.info("Crédit Agricole login successful (pro=%s)", self.is_pro)

    async def logout(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw_context:
            await self._pw_context.__aexit__(None, None, None)

    async def fetch_accounts(self) -> list[Account]:
        """Scrape account list from CA dashboard."""
        assert self._page is not None

        await self._page.goto(
            f"{self._base_url}/operations/synthese.html",
            wait_until="networkidle",
        )

        accounts = []
        inst_id = uuid.uuid5(uuid.NAMESPACE_DNS, "credit_agricole")
        rows = await self._page.query_selector_all('.ca-table tbody tr')

        for row in rows:
            cells = await row.query_selector_all('td')
            if len(cells) < 2:
                continue

            name = (await cells[0].inner_text()).strip()
            balance_text = (await cells[1].inner_text()).strip()
            balance = _parse_ca_amount(balance_text)
            account_type = _detect_ca_type(name)

            accounts.append(
                Account(
                    institution_id=inst_id,
                    name=name,
                    account_type=account_type,
                    currency="EUR",
                    balance=balance,
                    is_pro=self.is_pro,
                )
            )

        return accounts

    async def fetch_transactions(self, account: Account) -> list[Transaction]:
        """Scrape transactions from an account detail page."""
        assert self._page is not None

        transactions = []
        rows = await self._page.query_selector_all('.ca-operations-table tbody tr')

        for row in rows:
            cells = await row.query_selector_all('td')
            if len(cells) < 3:
                continue

            date_text = (await cells[0].inner_text()).strip()
            description = (await cells[1].inner_text()).strip()
            amount_text = (await cells[2].inner_text()).strip()

            transactions.append(
                Transaction(
                    account_id=account.id,
                    date=_parse_ca_date(date_text),
                    description=description,
                    amount=_parse_ca_amount(amount_text),
                )
            )

        return transactions


def _parse_ca_amount(text: str) -> Decimal:
    """Parse CA formatted amount: '1 234,56 €' or '-1 234,56 €'."""
    cleaned = (
        text.replace("€", "")
        .replace("\u202f", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
        .replace("−", "-")
        .replace("–", "-")
        .strip()
    )
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def _parse_ca_date(text: str) -> date:
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date.today()


def _detect_ca_type(name: str) -> AccountType:
    upper = name.upper()
    if "LIVRET" in upper or "LDD" in upper or "LEP" in upper or "EPARGNE" in upper:
        return AccountType.SAVINGS
    if "PRET" in upper or "PRÊT" in name.upper() or "CREDIT" in upper or "CRÉDIT" in name.upper() or "EMPRUNT" in upper:
        return AccountType.LOAN
    return AccountType.CHECKING
