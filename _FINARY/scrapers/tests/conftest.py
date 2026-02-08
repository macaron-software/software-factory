"""Shared fixtures for all tests."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scrapers.models import Account, AccountType, AssetType, Position

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_portfolio():
    """Load the full sample portfolio fixture."""
    with open(FIXTURES_DIR / "sample_portfolio.json") as f:
        return json.load(f)


@pytest.fixture
def ibkr_responses():
    """Load IBKR API mock responses."""
    with open(FIXTURES_DIR / "ibkr_responses.json") as f:
        return json.load(f)


@pytest.fixture
def ecb_xml():
    """Load ECB daily rates XML fixture."""
    return (FIXTURES_DIR / "ecb_daily.xml").read_text()


@pytest.fixture
def fx_rates() -> dict[str, Decimal]:
    """Standard FX rates for testing (EUR-based)."""
    return {
        "EUR": Decimal("1"),
        "USD": Decimal("1.0380"),
        "GBP": Decimal("0.8340"),
        "CHF": Decimal("0.9420"),
        "JPY": Decimal("157.80"),
    }


@pytest.fixture
def sample_accounts() -> list[Account]:
    """Sample accounts from the fixture data."""
    inst_ibkr = uuid.uuid5(uuid.NAMESPACE_DNS, "ibkr")
    inst_tr = uuid.uuid5(uuid.NAMESPACE_DNS, "trade_republic")
    inst_bourso = uuid.uuid5(uuid.NAMESPACE_DNS, "boursobank")
    inst_ca = uuid.uuid5(uuid.NAMESPACE_DNS, "credit_agricole")

    return [
        Account(
            institution_id=inst_ibkr,
            name="IBKR Brokerage USD",
            account_type=AccountType.CTO,
            currency="USD",
            balance=Decimal("87543.21"),
        ),
        Account(
            institution_id=inst_tr,
            name="Trade Republic CTO",
            account_type=AccountType.CTO,
            currency="EUR",
            balance=Decimal("23456.78"),
        ),
        Account(
            institution_id=inst_bourso,
            name="Bourso Compte Courant",
            account_type=AccountType.CHECKING,
            currency="EUR",
            balance=Decimal("4532.15"),
        ),
        Account(
            institution_id=inst_bourso,
            name="Bourso Livret A",
            account_type=AccountType.SAVINGS,
            currency="EUR",
            balance=Decimal("22950.00"),
        ),
        Account(
            institution_id=inst_bourso,
            name="Bourso PEA",
            account_type=AccountType.PEA,
            currency="EUR",
            balance=Decimal("45230.50"),
        ),
        Account(
            institution_id=inst_ca,
            name="CA Compte Courant Perso",
            account_type=AccountType.CHECKING,
            currency="EUR",
            balance=Decimal("3210.45"),
        ),
        Account(
            institution_id=inst_ca,
            name="CA Compte Pro",
            account_type=AccountType.CHECKING,
            currency="EUR",
            balance=Decimal("18750.30"),
            is_pro=True,
        ),
        Account(
            institution_id=inst_ca,
            name="CA Prêt Immobilier",
            account_type=AccountType.LOAN,
            currency="EUR",
            balance=Decimal("-185000.00"),
        ),
    ]


@pytest.fixture
def sample_positions() -> list[Position]:
    """Sample investment positions from fixture data."""
    acc_id = uuid.uuid4()
    return [
        Position(
            account_id=acc_id,
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
        ),
        Position(
            account_id=acc_id,
            ticker="MSFT",
            isin="US5949181045",
            name="Microsoft Corporation",
            quantity=Decimal("50"),
            avg_cost=Decimal("380.00"),
            current_price=Decimal("420.00"),
            currency="USD",
            asset_type=AssetType.STOCK,
            sector="Technology",
            country="US",
        ),
        Position(
            account_id=acc_id,
            ticker="VWCE.DE",
            isin="IE00BK5BQT80",
            name="Vanguard FTSE All-World UCITS ETF",
            quantity=Decimal("100"),
            avg_cost=Decimal("95.20"),
            current_price=Decimal("112.30"),
            currency="EUR",
            asset_type=AssetType.ETF,
        ),
        Position(
            account_id=acc_id,
            ticker="BNP.PA",
            isin="FR0000131104",
            name="BNP Paribas SA",
            quantity=Decimal("200"),
            avg_cost=Decimal("52.30"),
            current_price=Decimal("62.50"),
            currency="EUR",
            asset_type=AssetType.STOCK,
            sector="Financials",
            country="FR",
        ),
    ]
