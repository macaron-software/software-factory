"""Tests for ISIN ↔ Ticker resolution."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scrapers.market_data.isin_resolver import ISINResolver


@pytest.fixture
def resolver():
    """Resolver with mocked yfinance search."""
    mock_yf = MagicMock()
    mock_yf.search.return_value = [
        {"ticker": "TTE.PA", "name": "TotalEnergies SE", "exchange": "XPAR", "type": "EQUITY"}
    ]
    return ISINResolver(yfinance=mock_yf)


class TestISINResolver:
    def test_known_isin(self, resolver):
        """Known ISINs resolve from local cache."""
        result = resolver.resolve("IE00BK5BQT80")
        assert result["ticker"] == "VWCE.DE"
        assert result["name"] == "Vanguard FTSE All-World"

    def test_known_isin_apple(self, resolver):
        result = resolver.resolve("US0378331005")
        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."

    def test_ticker_passthrough(self, resolver):
        """Non-ISIN identifiers pass through as ticker."""
        result = resolver.resolve("AAPL")
        assert result["ticker"] == "AAPL"

    def test_unknown_isin_yahoo_fallback(self, resolver):
        """Unknown ISIN triggers Yahoo search."""
        result = resolver.resolve("FR0000120271")
        assert result["ticker"] == "TTE.PA"
        assert result["name"] == "TotalEnergies SE"

    def test_unknown_isin_cached_after_resolve(self, resolver):
        """Resolved ISIN should be cached for subsequent lookups."""
        resolver.resolve("FR0000120271")
        # Second call should hit cache (yfinance.search not called again)
        resolver._yfinance.search.reset_mock()
        result = resolver.resolve("FR0000120271")
        assert result["ticker"] == "TTE.PA"
        resolver._yfinance.search.assert_not_called()

    def test_is_isin_valid(self, resolver):
        assert resolver.is_isin("US0378331005")
        assert resolver.is_isin("IE00BK5BQT80")
        assert resolver.is_isin("FR0000120271")

    def test_is_isin_invalid(self, resolver):
        assert not resolver.is_isin("AAPL")
        assert not resolver.is_isin("VWCE.DE")
        assert not resolver.is_isin("123")
        assert not resolver.is_isin("")

    def test_manual_mapping(self, resolver):
        resolver.add_mapping("XX0000000001", "CUSTOM.PA", "Custom Stock", "XPAR")
        result = resolver.resolve("XX0000000001")
        assert result["ticker"] == "CUSTOM.PA"

    def test_resolve_failure(self):
        """When Yahoo search returns nothing, raise ValueError."""
        mock_yf = MagicMock()
        mock_yf.search.return_value = []
        resolver = ISINResolver(yfinance=mock_yf)
        with pytest.raises(ValueError, match="Cannot resolve"):
            resolver.resolve("ZZ9999999999")
