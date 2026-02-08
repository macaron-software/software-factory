"""Trade Republic scraper using Playwright.

TR uses a web app at app.traderepublic.com with strong anti-bot measures.
Auth: phone number → PIN → OTP SMS.
Data: positions, transactions, dividends, savings plans.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from scrapers.base import BaseScraper, OTPRequiredError
from scrapers.models import Account, AccountType, AssetType, Position, Transaction

_pw = None


def _get_playwright():
    global _pw
    if _pw is None:
        from playwright.async_api import async_playwright
        _pw = async_playwright
    return _pw


class TradeRepublicScraper(BaseScraper):
    institution_name = "trade_republic"
    display_name = "Trade Republic"
    scraper_type = "playwright"

    LOGIN_URL = "https://app.traderepublic.com/"

    def __init__(self, phone: str = "", pin: str = "") -> None:
        super().__init__()
        self.phone = phone
        self.pin = pin
        self._pw_context = None
        self._browser = None
        self._page = None

    async def login(self) -> None:
        pw = _get_playwright()
        self._pw_context = await pw().__aenter__()
        self._browser = await self._pw_context.chromium.launch(headless=True)
        ctx = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            viewport={"width": 390, "height": 844},  # mobile viewport
        )
        self._page = await ctx.new_page()

        await self._page.goto(self.LOGIN_URL, wait_until="networkidle")
        await self._page.wait_for_timeout(2000)  # anti-bot cooldown

        # Enter phone number
        phone_input = await self._page.query_selector('input[type="tel"]')
        if phone_input:
            await phone_input.fill(self.phone)
            await self._page.wait_for_timeout(500)

        # Click next
        next_btn = await self._page.query_selector('button[data-testid="login-next"]')
        if next_btn:
            await next_btn.click()
        await self._page.wait_for_timeout(1000)

        # Enter PIN (4 digits)
        for digit in self.pin:
            pin_input = await self._page.query_selector(f'input[data-testid="pin-input"]')
            if pin_input:
                await pin_input.type(digit, delay=100)

        await self._page.wait_for_timeout(1000)

        # Check for OTP (TR always requires SMS OTP)
        otp_el = await self._page.query_selector('[data-testid="otp-input"]')
        if otp_el:
            raise OTPRequiredError("sms")

        self.logger.info("Trade Republic login successful")

    async def logout(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw_context:
            await self._pw_context.__aexit__(None, None, None)

    async def fetch_accounts(self) -> list[Account]:
        """Fetch TR account overview."""
        assert self._page is not None

        await self._page.goto(
            "https://app.traderepublic.com/portfolio", wait_until="networkidle"
        )
        await self._page.wait_for_timeout(2000)

        inst_id = uuid.uuid5(uuid.NAMESPACE_DNS, "trade_republic")

        # Get total portfolio value
        value_el = await self._page.query_selector('[data-testid="portfolio-value"]')
        cash_el = await self._page.query_selector('[data-testid="cash-balance"]')

        portfolio_val = _parse_tr_amount(
            await value_el.inner_text() if value_el else "0"
        )
        cash_val = _parse_tr_amount(
            await cash_el.inner_text() if cash_el else "0"
        )

        accounts = [
            Account(
                institution_id=inst_id,
                name="Trade Republic CTO",
                account_type=AccountType.CTO,
                currency="EUR",
                balance=portfolio_val,
            ),
        ]
        if cash_val > 0:
            accounts.append(
                Account(
                    institution_id=inst_id,
                    name="Trade Republic Cash",
                    account_type=AccountType.CHECKING,
                    currency="EUR",
                    balance=cash_val,
                )
            )

        return accounts

    async def fetch_transactions(self, account: Account) -> list[Transaction]:
        """Fetch TR transactions (activity timeline)."""
        assert self._page is not None

        await self._page.goto(
            "https://app.traderepublic.com/profile/transactions",
            wait_until="networkidle",
        )
        await self._page.wait_for_timeout(2000)

        transactions = []
        rows = await self._page.query_selector_all('[data-testid="timeline-event"]')

        for row in rows:
            title_el = await row.query_selector('[data-testid="event-title"]')
            amount_el = await row.query_selector('[data-testid="event-amount"]')
            date_el = await row.query_selector('[data-testid="event-date"]')

            title = await title_el.inner_text() if title_el else ""
            amount = _parse_tr_amount(await amount_el.inner_text() if amount_el else "0")
            date_text = await date_el.inner_text() if date_el else ""

            transactions.append(
                Transaction(
                    account_id=account.id,
                    date=_parse_tr_date(date_text),
                    description=title.strip(),
                    amount=amount,
                    category="investissement",
                )
            )

        return transactions

    async def fetch_positions(self, account: Account) -> list[Position]:
        """Fetch TR positions."""
        assert self._page is not None

        if account.account_type != AccountType.CTO:
            return []

        await self._page.goto(
            "https://app.traderepublic.com/portfolio", wait_until="networkidle"
        )
        await self._page.wait_for_timeout(2000)

        positions = []
        rows = await self._page.query_selector_all('[data-testid="portfolio-instrument"]')

        for row in rows:
            name_el = await row.query_selector('[data-testid="instrument-name"]')
            isin_el = await row.query_selector('[data-testid="instrument-isin"]')
            qty_el = await row.query_selector('[data-testid="instrument-quantity"]')
            price_el = await row.query_selector('[data-testid="instrument-price"]')
            cost_el = await row.query_selector('[data-testid="instrument-avg-cost"]')

            name = await name_el.inner_text() if name_el else ""
            isin = (await isin_el.inner_text()).strip() if isin_el else None
            quantity = _parse_tr_amount(await qty_el.inner_text() if qty_el else "0")
            price = _parse_tr_amount(await price_el.inner_text() if price_el else "0")
            cost = _parse_tr_amount(await cost_el.inner_text() if cost_el else "0") or None

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


def _parse_tr_amount(text: str) -> Decimal:
    """Parse TR amount: '1.234,56 €' → Decimal('1234.56')."""
    cleaned = (
        text.replace("€", "")
        .replace("\u202f", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .strip()
    )
    # TR uses dot for thousands, comma for decimal
    cleaned = cleaned.replace(".", "").replace(",", ".")
    cleaned = cleaned.replace("−", "-").replace("–", "-")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def _parse_tr_date(text: str) -> date:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date.today()
