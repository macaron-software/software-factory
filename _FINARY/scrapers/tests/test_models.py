"""Tests for Pydantic models."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from scrapers.models import (
    Account,
    AccountType,
    AssetType,
    Dividend,
    ExchangeRate,
    NetWorth,
    PortfolioValuation,
    Position,
    PricePoint,
    SyncResult,
    SyncStatus,
    Transaction,
)


class TestAccount:
    def test_create_checking(self):
        acc = Account(
            institution_id=uuid.uuid4(),
            name="My Checking",
            account_type=AccountType.CHECKING,
            balance=Decimal("1234.56"),
        )
        assert acc.currency == "EUR"
        assert acc.is_pro is False
        assert acc.balance == Decimal("1234.56")

    def test_create_pro(self):
        acc = Account(
            institution_id=uuid.uuid4(),
            name="Pro Account",
            account_type=AccountType.CHECKING,
            is_pro=True,
        )
        assert acc.is_pro is True


class TestPosition:
    def test_create_stock(self):
        pos = Position(
            account_id=uuid.uuid4(),
            ticker="AAPL",
            isin="US0378331005",
            name="Apple Inc.",
            quantity=Decimal("150"),
            avg_cost=Decimal("178.50"),
            current_price=Decimal("230.50"),
            currency="USD",
            asset_type=AssetType.STOCK,
            sector="Technology",
            country="US",
        )
        assert pos.ticker == "AAPL"
        assert pos.asset_type == AssetType.STOCK

    def test_create_etf(self):
        pos = Position(
            account_id=uuid.uuid4(),
            ticker="VWCE.DE",
            name="Vanguard All-World",
            quantity=Decimal("100"),
            currency="EUR",
            asset_type=AssetType.ETF,
        )
        assert pos.asset_type == AssetType.ETF
        assert pos.isin is None


class TestTransaction:
    def test_create(self):
        tx = Transaction(
            account_id=uuid.uuid4(),
            date=date(2025, 2, 7),
            description="CARTE CARREFOUR",
            amount=Decimal("-45.32"),
        )
        assert tx.amount < 0
        assert tx.category is None


class TestPricePoint:
    def test_create(self):
        pp = PricePoint(
            ticker="AAPL",
            date=date(2025, 2, 7),
            open=Decimal("228.00"),
            high=Decimal("231.50"),
            low=Decimal("227.00"),
            close=Decimal("230.50"),
            volume=45000000,
            currency="USD",
        )
        assert pp.close == Decimal("230.50")


class TestSyncResult:
    def test_success(self):
        r = SyncResult(
            institution_name="ibkr",
            status=SyncStatus.SUCCESS,
            accounts_synced=1,
            transactions_added=5,
        )
        assert r.status == SyncStatus.SUCCESS

    def test_error(self):
        r = SyncResult(
            institution_name="boursobank",
            status=SyncStatus.ERROR,
            error_message="Connection timeout",
        )
        assert r.error_message == "Connection timeout"


class TestPortfolioValuation:
    def test_create(self):
        v = PortfolioValuation(
            ticker="AAPL",
            name="Apple Inc.",
            quantity=Decimal("150"),
            current_price=Decimal("230.50"),
            currency="USD",
            value_native=Decimal("34575"),
            value_eur=Decimal("33309.25"),
            pnl_native=Decimal("7800"),
            pnl_eur=Decimal("7512.52"),
            pnl_pct=Decimal("29.13"),
            weight_pct=Decimal("45.67"),
            asset_type=AssetType.STOCK,
        )
        assert v.value_native > v.value_eur  # USD > EUR rate


class TestNetWorth:
    def test_create(self):
        nw = NetWorth(
            total_assets=Decimal("250000"),
            total_liabilities=Decimal("185000"),
            net_worth=Decimal("65000"),
            breakdown={"cash": Decimal("30000"), "investments": Decimal("220000")},
            by_institution={"ibkr": Decimal("100000"), "bourso": Decimal("150000")},
            by_currency={"EUR": Decimal("200000"), "USD": Decimal("50000")},
        )
        assert nw.net_worth == nw.total_assets - nw.total_liabilities
