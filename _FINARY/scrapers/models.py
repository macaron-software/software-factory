"""Pydantic models shared across all scrapers and services."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    PEA = "pea"
    CTO = "cto"
    AV = "av"  # assurance-vie
    LOAN = "loan"
    CRYPTO = "crypto"


class AssetType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    BOND = "bond"
    CRYPTO = "crypto"
    FUND = "fund"
    OPTION = "option"


class SyncStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR = "error"
    OTP_REQUIRED = "otp_required"


class Institution(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    display_name: str
    scraper_type: str  # 'api', 'playwright', 'websocket'


class Account(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    institution_id: uuid.UUID
    external_id: str | None = None
    name: str
    account_type: AccountType
    currency: str = "EUR"
    balance: Decimal = Decimal("0")
    is_pro: bool = False


class Transaction(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    account_id: uuid.UUID
    external_id: str | None = None
    date: date
    description: str
    amount: Decimal
    category: str | None = None
    merchant: str | None = None


class Position(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    account_id: uuid.UUID
    ticker: str
    isin: str | None = None
    name: str
    quantity: Decimal
    avg_cost: Decimal | None = None
    current_price: Decimal | None = None
    currency: str = "EUR"
    asset_type: AssetType
    sector: str | None = None
    country: str | None = None


class Dividend(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    position_id: uuid.UUID
    ex_date: date | None = None
    pay_date: date | None = None
    amount_per_share: Decimal
    total_amount: Decimal
    currency: str = "EUR"


class PricePoint(BaseModel):
    ticker: str
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal
    volume: int | None = None
    currency: str = "EUR"


class ExchangeRate(BaseModel):
    date: date
    base_currency: str = "EUR"
    quote_currency: str
    rate: Decimal


class SyncResult(BaseModel):
    institution_name: str
    status: SyncStatus
    accounts_synced: int = 0
    transactions_added: int = 0
    positions_updated: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    error_message: str | None = None


class PortfolioValuation(BaseModel):
    """Valorisation d'une position avec conversion EUR."""
    ticker: str
    name: str
    quantity: Decimal
    current_price: Decimal
    currency: str
    value_native: Decimal
    value_eur: Decimal
    avg_cost: Decimal | None = None
    pnl_native: Decimal = Decimal("0")
    pnl_eur: Decimal = Decimal("0")
    pnl_pct: Decimal = Decimal("0")
    weight_pct: Decimal = Decimal("0")
    asset_type: AssetType
    sector: str | None = None
    country: str | None = None


class NetWorth(BaseModel):
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    breakdown: dict[str, Decimal]  # {class -> value}
    by_institution: dict[str, Decimal]
    by_currency: dict[str, Decimal]
