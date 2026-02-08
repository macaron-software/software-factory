"""Trade Republic scraper using WebSocket API.

TR uses a WebSocket-based API at wss://api.traderepublic.com.
Auth: phone + PIN → OTP (2FA always required).
Based on: github.com/omni-vi/pytr and neobroker-portfolio-importer.

Two modes:
  1. WebSocket API via pytr (full access — positions, timeline, documents)
  2. Playwright fallback (if pytr fails / anti-bot blocks)
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from scrapers.base import BaseScraper, OTPRequiredError
from scrapers.models import Account, AccountType, AssetType, Position, Transaction


class TradeRepublicScraper(BaseScraper):
    """TR scraper — prefers pytr WebSocket API, falls back to Playwright."""

    institution_name = "trade_republic"
    display_name = "Trade Republic"
    scraper_type = "websocket"

    def __init__(
        self,
        phone: str = "",
        pin: str = "",
        locale: str = "fr",
    ) -> None:
        super().__init__()
        self.phone = phone
        self.pin = pin
        self.locale = locale
        self._tr = None  # pytr TradeRepublicApi instance
        self._portfolio_raw: list = []
        self._cash: Decimal = Decimal("0")

    async def login(self) -> None:
        """Authenticate via pytr WebSocket API."""
        try:
            from pytr.api import TradeRepublicApi
        except ImportError:
            self.logger.warning("pytr not installed, falling back to Playwright")
            await self._login_playwright()
            return

        try:
            self._tr = TradeRepublicApi(
                phone_no=self.phone,
                pin=self.pin,
                locale=self.locale,
            )
            await self._tr.login()
            self.logger.info("Trade Republic WebSocket API connected")
        except Exception as e:
            err = str(e).lower()
            if "otp" in err or "2fa" in err or "verify" in err:
                raise OTPRequiredError("sms")
            raise

    async def _login_playwright(self) -> None:
        """Fallback: Playwright browser automation."""
        from playwright.async_api import async_playwright

        self._pw_ctx = await async_playwright().__aenter__()
        browser = await self._pw_ctx.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            viewport={"width": 390, "height": 844},
        )
        self._page = await ctx.new_page()
        self._browser = browser
        await self._page.goto("https://app.traderepublic.com/", wait_until="networkidle")
        # TR always requires OTP
        raise OTPRequiredError("sms")

    async def logout(self) -> None:
        if self._tr:
            try:
                await self._tr.close()
            except Exception:
                pass
        if hasattr(self, "_browser") and self._browser:
            await self._browser.close()
        if hasattr(self, "_pw_ctx") and self._pw_ctx:
            await self._pw_ctx.__aexit__(None, None, None)

    async def fetch_accounts(self) -> list[Account]:
        """Fetch TR accounts."""
        inst_id = uuid.uuid5(uuid.NAMESPACE_DNS, "trade_republic")

        if self._tr:
            return await self._fetch_accounts_ws(inst_id)

        # Fallback: return empty (would need Playwright)
        return []

    async def _fetch_accounts_ws(self, inst_id: uuid.UUID) -> list[Account]:
        """Fetch via WebSocket API."""
        # Get portfolio overview
        portfolio = await self._tr.portfolio()
        positions = portfolio.get("positions", [])
        self._portfolio_raw = positions

        total_value = sum(
            Decimal(str(p.get("netValue", 0))) for p in positions
        )

        # Get cash balance
        cash_resp = await self._tr.cash()
        self._cash = Decimal(str(cash_resp.get("value", 0)))

        accounts = [
            Account(
                institution_id=inst_id,
                name="Trade Republic CTO",
                account_type=AccountType.CTO,
                currency="EUR",
                balance=total_value,
            ),
        ]

        if self._cash > 0:
            accounts.append(
                Account(
                    institution_id=inst_id,
                    name="Trade Republic Cash",
                    account_type=AccountType.CHECKING,
                    currency="EUR",
                    balance=self._cash,
                )
            )

        return accounts

    async def fetch_transactions(self, account: Account) -> list[Transaction]:
        """Fetch TR transactions from timeline."""
        if not self._tr:
            return []

        try:
            timeline = await self._tr.timeline()
            events = timeline.get("items", [])
        except Exception as e:
            self.logger.warning("Failed to fetch TR timeline: %s", e)
            return []

        transactions = []
        for event in events:
            event_type = event.get("type", "")
            title = event.get("title", "")
            amount_data = event.get("amount", {})
            amount = Decimal(str(amount_data.get("value", 0)))
            currency = amount_data.get("currency", "EUR")

            # Parse date
            ts = event.get("timestamp")
            try:
                tx_date = datetime.fromisoformat(ts).date() if ts else date.today()
            except (ValueError, TypeError):
                tx_date = date.today()

            # Categorize
            category = "investissement"
            if event_type in ("SAVINGS_PLAN", "ORDER_EXECUTED"):
                category = "investissement"
            elif event_type in ("INTEREST_PAYOUT",):
                category = "interets"
            elif event_type in ("DIVIDEND",):
                category = "dividende"

            transactions.append(
                Transaction(
                    account_id=account.id,
                    external_id=event.get("id"),
                    date=tx_date,
                    description=title,
                    amount=amount,
                    category=category,
                )
            )

        return transactions

    async def fetch_positions(self, account: Account) -> list[Position]:
        """Fetch TR positions."""
        if account.account_type != AccountType.CTO:
            return []

        if not self._tr:
            return []

        positions = []
        for raw in self._portfolio_raw:
            isin = raw.get("instrumentId", "")
            name = raw.get("name", isin)
            quantity = Decimal(str(raw.get("netSize", 0)))
            avg_cost = Decimal(str(raw.get("averageBuyIn", 0)))
            current_price = Decimal(str(raw.get("currentPrice", {}).get("price", 0)))

            # Detect asset type from instrument info
            instrument_type = raw.get("instrumentType", "").upper()
            if "ETF" in instrument_type or "ETF" in name.upper():
                asset_type = AssetType.ETF
            elif "CRYPTO" in instrument_type:
                asset_type = AssetType.CRYPTO
            elif "BOND" in instrument_type:
                asset_type = AssetType.BOND
            else:
                asset_type = AssetType.STOCK

            positions.append(
                Position(
                    account_id=account.id,
                    ticker=isin,
                    isin=isin if len(isin) == 12 else None,
                    name=name,
                    quantity=quantity,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    currency="EUR",
                    asset_type=asset_type,
                )
            )

        return positions
