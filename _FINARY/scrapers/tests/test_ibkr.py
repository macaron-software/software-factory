"""Tests for IBKR scraper using mocked HTTP responses."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.ibkr.scraper import IBKRScraper
from scrapers.models import AccountType, AssetType

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ibkr_data():
    with open(FIXTURES / "ibkr_responses.json") as f:
        return json.load(f)


class MockResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@pytest.fixture
def mock_ibkr_client(ibkr_data):
    """Mock httpx.AsyncClient for IBKR API calls."""
    client = AsyncMock()

    async def mock_post(url, **kwargs):
        if "auth/status" in url:
            return MockResponse(ibkr_data["auth_status"])
        return MockResponse({})

    async def mock_get(url, **kwargs):
        if "iserver/accounts" in url:
            return MockResponse(ibkr_data["accounts"])
        if "summary" in url:
            return MockResponse(ibkr_data["summary"])
        if "positions" in url:
            return MockResponse(ibkr_data["positions"])
        if "trades" in url:
            return MockResponse(ibkr_data["trades"])
        return MockResponse({})

    client.post = mock_post
    client.get = mock_get
    client.aclose = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_ibkr_login(mock_ibkr_client):
    scraper = IBKRScraper()
    scraper.client = mock_ibkr_client
    await scraper.login()
    assert scraper._account_id == "U12345678"


@pytest.mark.asyncio
async def test_ibkr_fetch_accounts(mock_ibkr_client):
    scraper = IBKRScraper()
    scraper.client = mock_ibkr_client
    scraper._account_id = "U12345678"

    accounts = await scraper.fetch_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "IBKR U12345678"
    assert accounts[0].account_type == AccountType.CTO
    assert accounts[0].currency == "USD"
    assert accounts[0].balance == Decimal("87543.21")


@pytest.mark.asyncio
async def test_ibkr_fetch_positions(mock_ibkr_client):
    scraper = IBKRScraper()
    scraper.client = mock_ibkr_client
    scraper._account_id = "U12345678"

    from scrapers.models import Account
    import uuid

    account = Account(
        institution_id=uuid.uuid4(),
        name="IBKR",
        account_type=AccountType.CTO,
        currency="USD",
        balance=Decimal("87543.21"),
    )
    positions = await scraper.fetch_positions(account)

    assert len(positions) == 3
    # Check AAPL
    aapl = next(p for p in positions if p.ticker == "AAPL")
    assert aapl.quantity == Decimal("150")
    assert aapl.avg_cost == Decimal("178.50")
    assert aapl.current_price == Decimal("230.50")
    assert aapl.currency == "USD"
    assert aapl.asset_type == AssetType.STOCK

    # Check VWCE (EUR position)
    vwce = next(p for p in positions if "VWCE" in p.ticker)
    assert vwce.currency == "EUR"
    assert vwce.quantity == Decimal("100")


@pytest.mark.asyncio
async def test_ibkr_fetch_transactions(mock_ibkr_client):
    scraper = IBKRScraper()
    scraper.client = mock_ibkr_client
    scraper._account_id = "U12345678"

    from scrapers.models import Account
    import uuid

    account = Account(
        institution_id=uuid.uuid4(),
        name="IBKR",
        account_type=AccountType.CTO,
        currency="USD",
        balance=Decimal("0"),
    )
    transactions = await scraper.fetch_transactions(account)

    assert len(transactions) == 2
    assert "AAPL" in transactions[0].description
    assert transactions[0].amount == Decimal("-2250")
    assert transactions[0].category == "investissement"


@pytest.mark.asyncio
async def test_ibkr_full_sync(mock_ibkr_client):
    """Test full sync flow."""
    scraper = IBKRScraper()
    scraper.client = mock_ibkr_client

    result = await scraper.sync()
    assert result.status.value == "success"
    assert result.accounts_synced == 1
    assert result.transactions_added == 2
    assert result.positions_updated == 3
