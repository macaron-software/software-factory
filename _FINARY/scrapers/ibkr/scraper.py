"""Interactive Brokers scraper using ib_async (successor to ib_insync).

ib_async provides a Pythonic async interface to the IBKR TWS/Gateway API.
Reference: github.com/ib-api-reloaded/ib_async

Two modes:
  1. TWS API via ib_async (recommended — full feature access)
  2. Client Portal REST API fallback (simpler setup)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx

from scrapers.base import BaseScraper
from scrapers.models import Account, AccountType, AssetType, Position, Transaction


# Asset class mapping
_ASSET_MAP = {
    "STK": AssetType.STOCK,
    "ETF": AssetType.ETF,
    "OPT": AssetType.OPTION,
    "BOND": AssetType.BOND,
    "CRYPTO": AssetType.CRYPTO,
    "CASH": AssetType.FUND,
    "FUT": AssetType.OPTION,
}


class IBKRScraper(BaseScraper):
    """IBKR scraper — prefers ib_async TWS API, falls back to Client Portal REST."""

    institution_name = "ibkr"
    display_name = "Interactive Brokers"
    scraper_type = "api"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,  # 7497=TWS paper, 7496=TWS live, 4002=Gateway paper, 4001=Gateway live
        client_id: int = 1,
        use_tws: bool = True,
        gateway_url: str = "https://localhost:5000/v1/api",
    ) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.use_tws = use_tws
        self.gateway_url = gateway_url
        self._ib = None  # ib_async.IB instance
        self._http = None  # httpx client for REST fallback
        self._account_id: str | None = None

    async def login(self) -> None:
        if self.use_tws:
            await self._login_tws()
        else:
            await self._login_rest()

    async def _login_tws(self) -> None:
        """Connect via ib_async TWS API."""
        try:
            from ib_async import IB
        except ImportError:
            self.logger.warning("ib_async not installed, falling back to REST API")
            self.use_tws = False
            await self._login_rest()
            return

        self._ib = IB()
        await self._ib.connectAsync(self.host, self.port, clientId=self.client_id)
        accounts = self._ib.managedAccounts()
        if accounts:
            self._account_id = accounts[0]
        self.logger.info("IBKR TWS connected, account: %s", self._account_id)

    async def _login_rest(self) -> None:
        """Connect via Client Portal REST API (fallback)."""
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.gateway_url, verify=False, timeout=30)
        r = await self._http.post("/iserver/auth/status")
        data = r.json()
        if not data.get("authenticated"):
            await self._http.post("/iserver/reauthenticate")
            r = await self._http.post("/iserver/auth/status")
            data = r.json()
            if not data.get("authenticated"):
                raise ConnectionError("IBKR gateway not authenticated.")
        r = await self._http.get("/iserver/accounts")
        accounts_data = r.json()
        if accounts_data.get("accounts"):
            self._account_id = accounts_data["accounts"][0]
        self.logger.info("IBKR REST connected, account: %s", self._account_id)

    async def logout(self) -> None:
        if self._ib:
            self._ib.disconnect()
        if self._http:
            await self._http.aclose()

    async def fetch_accounts(self) -> list[Account]:
        if self.use_tws and self._ib:
            return await self._fetch_accounts_tws()
        return await self._fetch_accounts_rest()

    async def _fetch_accounts_tws(self) -> list[Account]:
        """Fetch account summary via ib_async."""
        summary = await self._ib.accountSummaryAsync()
        nav = Decimal("0")
        currency = "USD"
        for item in summary:
            if item.tag == "NetLiquidation":
                nav = Decimal(str(item.value))
                currency = item.currency
                break

        return [
            Account(
                institution_id=uuid.uuid5(uuid.NAMESPACE_DNS, "ibkr"),
                external_id=self._account_id,
                name=f"IBKR {self._account_id}",
                account_type=AccountType.CTO,
                currency=currency,
                balance=nav,
            )
        ]

    async def _fetch_accounts_rest(self) -> list[Account]:
        """Fetch account summary via REST API."""
        r = await self._http.get(f"/portfolio/{self._account_id}/summary")
        summary = r.json()
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
        if self.use_tws and self._ib:
            return await self._fetch_transactions_tws(account)
        return await self._fetch_transactions_rest(account)

    async def _fetch_transactions_tws(self, account: Account) -> list[Transaction]:
        """Fetch trades via ib_async executions API."""
        from ib_async import ExecutionFilter
        filt = ExecutionFilter(acctCode=self._account_id)
        executions = await self._ib.reqExecutionsAsync(filt)

        transactions = []
        for fill in executions:
            ex = fill.execution
            transactions.append(
                Transaction(
                    account_id=account.id,
                    external_id=ex.execId,
                    date=datetime.strptime(ex.time, "%Y%m%d %H:%M:%S").date() if ex.time else date.today(),
                    description=f"{ex.side} {fill.contract.symbol} x{ex.shares}",
                    amount=Decimal(str(ex.shares * ex.price * (-1 if ex.side == "BOT" else 1))),
                    category="investissement",
                )
            )
        return transactions

    async def _fetch_transactions_rest(self, account: Account) -> list[Transaction]:
        """Fetch trades via REST API."""
        r = await self._http.get("/iserver/account/trades")
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
        if self.use_tws and self._ib:
            return await self._fetch_positions_tws(account)
        return await self._fetch_positions_rest(account)

    async def _fetch_positions_tws(self, account: Account) -> list[Position]:
        """Fetch positions via ib_async portfolio API."""
        portfolio = self._ib.portfolio(self._account_id)
        positions = []
        for item in portfolio:
            contract = item.contract
            asset_type = _ASSET_MAP.get(contract.secType, AssetType.STOCK)
            positions.append(
                Position(
                    account_id=account.id,
                    ticker=contract.symbol,
                    isin=getattr(contract, "isin", None),
                    name=contract.localSymbol or contract.symbol,
                    quantity=Decimal(str(item.position)),
                    avg_cost=Decimal(str(item.averageCost)),
                    current_price=Decimal(str(item.marketPrice)),
                    currency=contract.currency,
                    asset_type=asset_type,
                )
            )
        return positions

    async def _fetch_positions_rest(self, account: Account) -> list[Position]:
        """Fetch positions via REST API."""
        r = await self._http.get(f"/portfolio/{self._account_id}/positions/0")
        positions_data = r.json()
        if not isinstance(positions_data, list):
            return []
        positions = []
        for p in positions_data:
            ticker = p.get("ticker", p.get("contractDesc", ""))
            asset_class = p.get("assetClass", "STK")
            asset_type = _ASSET_MAP.get(asset_class, AssetType.STOCK)
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
