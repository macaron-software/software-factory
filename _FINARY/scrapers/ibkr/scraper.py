"""Interactive Brokers scraper using Client Portal API.

IBKR Client Portal Gateway exposes a REST API on localhost:5000.
The gateway must be running (java -jar clientportal.gw/bin/run.sh).
Auth: session token via /iserver/auth/ssodh/init then /tickle to keep alive.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import httpx

from scrapers.base import BaseScraper
from scrapers.models import Account, AccountType, AssetType, Position, Transaction


class IBKRScraper(BaseScraper):
    institution_name = "ibkr"
    display_name = "Interactive Brokers"
    scraper_type = "api"

    BASE_URL = "https://localhost:5000/v1/api"

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__()
        self.base_url = base_url or self.BASE_URL
        self.client = httpx.AsyncClient(base_url=self.base_url, verify=False, timeout=30)
        self._account_id: str | None = None

    async def login(self) -> None:
        """Validate existing session (gateway handles auth via browser)."""
        r = await self.client.post("/iserver/auth/status")
        data = r.json()
        if not data.get("authenticated"):
            # Try to re-authenticate
            await self.client.post("/iserver/reauthenticate")
            r = await self.client.post("/iserver/auth/status")
            data = r.json()
            if not data.get("authenticated"):
                raise ConnectionError("IBKR gateway not authenticated. Open browser to authenticate.")
        # Get account ID
        r = await self.client.get("/iserver/accounts")
        accounts_data = r.json()
        if accounts_data.get("accounts"):
            self._account_id = accounts_data["accounts"][0]
        self.logger.info("IBKR authenticated, account: %s", self._account_id)

    async def logout(self) -> None:
        await self.client.aclose()

    async def fetch_accounts(self) -> list[Account]:
        """Fetch IBKR account summary."""
        r = await self.client.get(f"/portfolio/{self._account_id}/summary")
        summary = r.json()

        balance = Decimal(str(summary.get("totalcashvalue", {}).get("amount", 0)))
        nav = Decimal(str(summary.get("netliquidation", {}).get("amount", 0)))

        return [
            Account(
                institution_id=uuid.uuid5(uuid.NAMESPACE_DNS, "ibkr"),
                external_id=self._account_id,
                name=f"IBKR {self._account_id}",
                account_type=AccountType.CTO,
                currency=summary.get("netliquidation", {}).get("currency", "USD"),
                balance=nav,
            )
        ]

    async def fetch_transactions(self, account: Account) -> list[Transaction]:
        """Fetch recent trades from IBKR."""
        r = await self.client.get("/iserver/account/trades")
        trades = r.json()
        if not isinstance(trades, list):
            return []

        transactions = []
        for trade in trades:
            transactions.append(
                Transaction(
                    account_id=account.id,
                    external_id=trade.get("execution_id"),
                    date=datetime.fromtimestamp(
                        trade.get("trade_time_r", 0) / 1000
                    ).date() if trade.get("trade_time_r") else date.today(),
                    description=f"{trade.get('side', '')} {trade.get('symbol', '')} x{trade.get('size', '')}",
                    amount=Decimal(str(trade.get("net_amount", 0))),
                    category="investissement",
                )
            )
        return transactions

    async def fetch_positions(self, account: Account) -> list[Position]:
        """Fetch current positions from IBKR."""
        r = await self.client.get(f"/portfolio/{self._account_id}/positions/0")
        positions_data = r.json()
        if not isinstance(positions_data, list):
            return []

        positions = []
        for p in positions_data:
            ticker = p.get("ticker", p.get("contractDesc", ""))
            asset_class = p.get("assetClass", "STK")
            asset_type = {
                "STK": AssetType.STOCK,
                "ETF": AssetType.ETF,
                "OPT": AssetType.OPTION,
                "BOND": AssetType.BOND,
                "CRYPTO": AssetType.CRYPTO,
            }.get(asset_class, AssetType.STOCK)

            positions.append(
                Position(
                    account_id=account.id,
                    ticker=ticker,
                    isin=p.get("isin"),
                    name=p.get("contractDesc", ticker),
                    quantity=Decimal(str(p.get("position", 0))),
                    avg_cost=Decimal(str(p.get("avgCost", 0))),
                    current_price=Decimal(str(p.get("mktPrice", 0))),
                    currency=p.get("currency", "USD"),
                    asset_type=asset_type,
                )
            )
        return positions
