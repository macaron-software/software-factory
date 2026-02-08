"""Tests for analytics.dividends — yield and projections."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scrapers.analytics.dividends import dividend_yield, project_dividends
from scrapers.models import AssetType, PortfolioValuation


def _pos(ticker: str, name: str, value: float, country: str = "FR") -> PortfolioValuation:
    return PortfolioValuation(
        ticker=ticker,
        name=name,
        quantity=Decimal("100"),
        current_price=Decimal(str(value / 100)),
        currency="EUR",
        value_native=Decimal(str(value)),
        value_eur=Decimal(str(value)),
        asset_type=AssetType.STOCK,
        country=country,
    )


class TestDividendYield:
    def test_known_stock(self):
        positions = [_pos("FR0000120271", "TotalEnergies", 10000)]
        result = dividend_yield(positions)
        assert result.total_yield > 5.0  # TotalEnergies ~5.43%
        assert result.projected_annual > 500

    def test_mixed_portfolio(self):
        positions = [
            _pos("FR0000120271", "TotalEnergies", 10000),
            _pos("US0378331005", "Apple", 10000, "US"),
        ]
        result = dividend_yield(positions)
        assert result.total_yield > 0
        assert len(result.positions) >= 1

    def test_monthly_distribution(self):
        positions = [_pos("FR0000120271", "TotalEnergies", 10000)]
        result = dividend_yield(positions)
        assert len(result.projected_monthly) == 12
        assert sum(result.projected_monthly) > 0

    def test_empty(self):
        result = dividend_yield([])
        assert result.total_yield == 0.0


class TestProjectDividends:
    def test_growth(self):
        positions = [_pos("FR0000120271", "TotalEnergies", 10000)]
        projections = project_dividends(positions, [], growth_rate=0.05, years=5)
        assert len(projections) == 5
        # Each year should grow
        for i in range(1, len(projections)):
            assert projections[i] > projections[i - 1]
