"""Tests for analytics.fees — fee scanner."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scrapers.analytics.fees import compute_fees, projected_savings
from scrapers.models import AssetType, PortfolioValuation


def _pos(ticker: str, name: str, value: float, asset_type: AssetType = AssetType.ETF) -> PortfolioValuation:
    return PortfolioValuation(
        ticker=ticker,
        name=name,
        quantity=Decimal("100"),
        current_price=Decimal(str(value / 100)),
        currency="EUR",
        value_native=Decimal(str(value)),
        value_eur=Decimal(str(value)),
        asset_type=asset_type,
    )


class TestComputeFees:
    def test_known_etf(self):
        positions = [_pos("IE00BK5BQT80", "Vanguard FTSE All-World", 50000)]
        result = compute_fees(positions)
        assert result.total_value == 50000.0
        # TER = 0.22%
        assert abs(result.total_annual_fees - 110.0) < 1
        assert result.positions[0].source == "known"

    def test_stock_no_ter(self):
        positions = [_pos("AAPL", "Apple Inc.", 30000, AssetType.STOCK)]
        result = compute_fees(positions)
        assert result.total_annual_fees == 0.0

    def test_mixed_portfolio(self):
        positions = [
            _pos("IE00BK5BQT80", "VWCE", 50000),
            _pos("AAPL", "Apple", 20000, AssetType.STOCK),
            _pos("FR0010315770", "Lyxor MSCI World", 30000),
        ]
        result = compute_fees(positions)
        assert result.total_value == 100000.0
        assert result.total_annual_fees > 0
        assert result.weighted_ter > 0
        assert len(result.positions) == 3

    def test_empty(self):
        result = compute_fees([])
        assert result.total_value == 0.0


class TestProjectedSavings:
    def test_savings_over_10y(self):
        savings = projected_savings(0.015, 0.002, 10)
        assert savings > 0  # Cheaper fees = more money

    def test_same_fees(self):
        assert projected_savings(0.002, 0.002, 10) == 0.0
