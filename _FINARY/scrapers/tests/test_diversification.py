"""Tests for analytics.diversification — HHI, sector, geo scores."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from scrapers.analytics.diversification import (
    asset_class_breakdown,
    geo_score,
    hhi_score,
    sector_score,
)
from scrapers.models import AssetType, PortfolioValuation


def _make_position(
    ticker: str,
    name: str,
    value: float,
    sector: str | None = None,
    country: str | None = None,
    asset_type: AssetType = AssetType.STOCK,
) -> PortfolioValuation:
    return PortfolioValuation(
        ticker=ticker,
        name=name,
        quantity=Decimal("10"),
        current_price=Decimal(str(value / 10)),
        currency="EUR",
        value_native=Decimal(str(value)),
        value_eur=Decimal(str(value)),
        asset_type=asset_type,
        sector=sector,
        country=country,
    )


class TestHHI:
    def test_single_holding(self):
        assert hhi_score([1.0]) == 10000.0

    def test_equal_two(self):
        assert hhi_score([0.5, 0.5]) == 5000.0

    def test_equal_ten(self):
        result = hhi_score([0.1] * 10)
        assert abs(result - 1000.0) < 0.1

    def test_empty(self):
        assert hhi_score([]) == 10000.0


class TestSectorScore:
    def test_diversified(self):
        positions = [
            _make_position("A", "Tech Co", 1000, sector="Technology", country="US"),
            _make_position("B", "Health Co", 1000, sector="Healthcare", country="US"),
            _make_position("C", "Finance Co", 1000, sector="Financials", country="FR"),
            _make_position("D", "Energy Co", 1000, sector="Energy", country="GB"),
            _make_position("E", "Consumer Co", 1000, sector="Consumer Discretionary", country="DE"),
        ]
        result = sector_score(positions)
        assert result.score >= 5  # Moderately diversified (5 sectors)
        assert result.hhi == 2000.0  # 5 equal sectors = 5 * 20^2

    def test_concentrated(self):
        positions = [
            _make_position("A", "Tech 1", 9000, sector="Technology"),
            _make_position("B", "Tech 2", 1000, sector="Financials"),
        ]
        result = sector_score(positions)
        assert result.score <= 4  # Concentrated
        assert result.top_concentration == "Technology"
        assert result.top_weight == 90.0

    def test_empty(self):
        result = sector_score([])
        assert result.score == 1


class TestGeoScore:
    def test_global(self):
        positions = [
            _make_position("A", "US Co", 3000, country="US"),
            _make_position("B", "FR Co", 3000, country="FR"),
            _make_position("C", "JP Co", 3000, country="JP"),
            _make_position("D", "BR Co", 1000, country="BR"),
        ]
        result = geo_score(positions)
        assert result.score >= 4  # 4 regions with unequal weights
        assert len(result.breakdown) >= 3

    def test_single_country(self):
        positions = [
            _make_position("A", "FR 1", 5000, country="FR"),
            _make_position("B", "FR 2", 5000, country="FR"),
        ]
        result = geo_score(positions)
        assert result.score <= 2  # All in one region


class TestAssetClassBreakdown:
    def test_mixed(self):
        positions = [
            _make_position("A", "Stock", 5000, asset_type=AssetType.STOCK),
            _make_position("B", "ETF", 3000, asset_type=AssetType.ETF),
            _make_position("C", "Bond", 2000, asset_type=AssetType.BOND),
        ]
        result = asset_class_breakdown(positions)
        assert result["stock"] == 50.0
        assert result["etf"] == 30.0
        assert result["bond"] == 20.0

    def test_empty(self):
        assert asset_class_breakdown([]) == {}
