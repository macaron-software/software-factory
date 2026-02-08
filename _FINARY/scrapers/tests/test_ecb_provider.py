"""Tests for ECB FX provider."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from scrapers.market_data.ecb_provider import ECBProvider

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ecb_provider():
    return ECBProvider()


class TestECBConversion:
    def test_eur_to_eur(self, ecb_provider):
        rates = {"USD": Decimal("1.0380"), "EUR": Decimal("1")}
        result = ecb_provider.convert_to_eur(Decimal("100"), "EUR", rates)
        assert result == Decimal("100")

    def test_usd_to_eur(self, ecb_provider):
        rates = {"USD": Decimal("1.0380")}
        result = ecb_provider.convert_to_eur(Decimal("103.80"), "USD", rates)
        assert result == Decimal("100.00")

    def test_gbp_to_eur(self, ecb_provider):
        rates = {"GBP": Decimal("0.8340")}
        result = ecb_provider.convert_to_eur(Decimal("83.40"), "GBP", rates)
        assert result == Decimal("100.00")

    def test_unknown_currency_raises(self, ecb_provider):
        with pytest.raises(ValueError, match="No ECB rate"):
            ecb_provider.convert_to_eur(Decimal("100"), "XYZ", {})

    def test_convert_from_eur(self, ecb_provider):
        rates = {"USD": Decimal("1.0380")}
        result = ecb_provider.convert_from_eur(Decimal("100"), "USD", rates)
        assert result == Decimal("103.80")


class TestECBDailyRates:
    @pytest.mark.asyncio
    async def test_parse_daily_xml(self, ecb_xml, ecb_provider):
        """Test parsing of ECB XML response."""
        import httpx

        mock_response = MagicMock()
        mock_response.text = ecb_xml
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        import scrapers.market_data.ecb_provider as ecb_mod

        original = httpx.AsyncClient
        ecb_mod.httpx.AsyncClient = lambda **kwargs: mock_client

        try:
            rates = await ecb_provider.get_daily_rates()

            assert "USD" in rates
            assert "GBP" in rates
            assert "CHF" in rates
            assert "JPY" in rates
            assert "EUR" in rates

            assert rates["USD"] == Decimal("1.0380")
            assert rates["GBP"] == Decimal("0.8340")
            assert rates["CHF"] == Decimal("0.9420")
            assert rates["JPY"] == Decimal("157.80")
        finally:
            ecb_mod.httpx.AsyncClient = original
