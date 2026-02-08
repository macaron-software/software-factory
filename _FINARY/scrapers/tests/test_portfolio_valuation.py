"""Tests for portfolio valuation and net worth calculation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scrapers.market_data.portfolio_valuation import compute_net_worth, value_positions
from scrapers.models import AssetType, Position


class TestValuePositions:
    def test_eur_positions(self, sample_positions, fx_rates):
        """Test valuation of EUR-denominated positions."""
        eur_positions = [p for p in sample_positions if p.currency == "EUR"]
        valuations, total = value_positions(eur_positions, fx_rates)

        assert len(valuations) == 2  # VWCE + BNP

        # VWCE: 100 × 112.30 = 11,230 EUR
        vwce = next(v for v in valuations if v.ticker == "VWCE.DE")
        assert vwce.value_native == Decimal("11230.0")
        assert vwce.value_eur == Decimal("11230.0")  # already EUR
        assert vwce.pnl_native == Decimal("1710.0")  # (112.30 - 95.20) × 100
        assert vwce.pnl_pct == Decimal("17.96")  # 1710/9520 * 100

        # BNP: 200 × 62.50 = 12,500 EUR
        bnp = next(v for v in valuations if v.ticker == "BNP.PA")
        assert bnp.value_native == Decimal("12500.0")
        assert bnp.pnl_native == Decimal("2040.0")  # (62.50 - 52.30) × 200

        # Total
        assert total == Decimal("23730.0")  # 11230 + 12500

    def test_usd_positions_fx_conversion(self, sample_positions, fx_rates):
        """Test that USD positions are converted to EUR correctly."""
        usd_positions = [p for p in sample_positions if p.currency == "USD"]
        valuations, total = value_positions(usd_positions, fx_rates)

        assert len(valuations) == 2  # AAPL + MSFT

        # AAPL: 150 × 230.50 = $34,575 → 34575/1.0380 = 33,309.25 EUR
        aapl = next(v for v in valuations if v.ticker == "AAPL")
        assert aapl.value_native == Decimal("34575.0")
        assert aapl.currency == "USD"
        # EUR value: 34575 / 1.0380 ≈ 33309.25
        assert abs(aapl.value_eur - Decimal("33309.25")) < Decimal("1")

        # MSFT: 50 × 420 = $21,000 → 21000/1.0380 ≈ 20231.21 EUR
        msft = next(v for v in valuations if v.ticker == "MSFT")
        assert msft.value_native == Decimal("21000.0")
        assert abs(msft.value_eur - Decimal("20231.21")) < Decimal("1")

    def test_mixed_currency_weights(self, sample_positions, fx_rates):
        """Test that weights sum to 100%."""
        valuations, total = value_positions(sample_positions, fx_rates)
        assert len(valuations) == 4

        total_weight = sum(v.weight_pct for v in valuations)
        assert abs(total_weight - Decimal("100")) < Decimal("0.1")

    def test_zero_cost_position(self, fx_rates):
        """Position with no avg_cost should have 0 P&L."""
        import uuid

        pos = Position(
            account_id=uuid.uuid4(),
            ticker="TEST",
            name="Test",
            quantity=Decimal("10"),
            avg_cost=None,
            current_price=Decimal("100"),
            currency="EUR",
            asset_type=AssetType.STOCK,
        )
        valuations, total = value_positions([pos], fx_rates)
        assert valuations[0].pnl_native == Decimal("1000")  # 10×100 - 0
        assert valuations[0].pnl_pct == Decimal("0")  # can't compute % with no cost

    def test_empty_positions(self, fx_rates):
        valuations, total = value_positions([], fx_rates)
        assert valuations == []
        assert total == Decimal("0")


class TestNetWorth:
    def test_basic_net_worth(self, fx_rates):
        accounts = [
            {"name": "CC", "type": "checking", "balance": 5000, "currency": "EUR", "institution": "boursobank"},
            {"name": "Livret", "type": "savings", "balance": 22000, "currency": "EUR", "institution": "boursobank"},
            {"name": "CC Pro", "type": "checking", "balance": 18000, "currency": "EUR", "institution": "ca"},
        ]
        nw = compute_net_worth(accounts, Decimal("70000"), rates=fx_rates)

        assert nw.total_assets == Decimal("115000")  # 5000 + 22000 + 18000 + 70000
        assert nw.total_liabilities == Decimal("0")
        assert nw.net_worth == Decimal("115000")
        assert nw.breakdown["cash"] == Decimal("23000")  # 5000 + 18000
        assert nw.breakdown["savings"] == Decimal("22000")
        assert nw.breakdown["investments"] == Decimal("70000")

    def test_net_worth_with_loan(self, fx_rates):
        accounts = [
            {"name": "CC", "type": "checking", "balance": 5000, "currency": "EUR", "institution": "bourso"},
            {"name": "Loan", "type": "loan", "balance": -185000, "currency": "EUR", "institution": "ca"},
        ]
        real_estate = [
            {"estimated_value": 480000, "loan_remaining": 185000},
        ]
        nw = compute_net_worth(accounts, Decimal("50000"), real_estate=real_estate, rates=fx_rates)

        assert nw.total_assets == Decimal("535000")  # 5000 + 50000 + 480000
        assert nw.total_liabilities == Decimal("370000")  # 185000 (account loan) + 185000 (RE loan)
        assert nw.net_worth == Decimal("165000")

    def test_net_worth_usd_accounts(self, fx_rates):
        """USD accounts should be converted to EUR."""
        accounts = [
            {"name": "IBKR", "type": "checking", "balance": 10380, "currency": "USD", "institution": "ibkr"},
        ]
        nw = compute_net_worth(accounts, Decimal("0"), rates=fx_rates)
        # $10,380 / 1.0380 = €10,000
        assert nw.breakdown["cash"] == Decimal("10000.00")

    def test_by_institution(self, fx_rates):
        accounts = [
            {"name": "CC1", "type": "checking", "balance": 3000, "currency": "EUR", "institution": "boursobank"},
            {"name": "CC2", "type": "checking", "balance": 5000, "currency": "EUR", "institution": "ca"},
            {"name": "Livret", "type": "savings", "balance": 10000, "currency": "EUR", "institution": "boursobank"},
        ]
        nw = compute_net_worth(accounts, Decimal("0"), rates=fx_rates)
        assert nw.by_institution["boursobank"] == Decimal("13000")  # 3000 + 10000
        assert nw.by_institution["ca"] == Decimal("5000")

    def test_by_currency(self, fx_rates):
        accounts = [
            {"name": "EUR acc", "type": "checking", "balance": 5000, "currency": "EUR", "institution": "x"},
            {"name": "USD acc", "type": "checking", "balance": 5000, "currency": "USD", "institution": "x"},
        ]
        nw = compute_net_worth(accounts, Decimal("0"), rates=fx_rates)
        assert nw.by_currency["EUR"] == Decimal("5000")
        # USD: $5000 / 1.0380 ≈ €4816.96
        assert abs(nw.by_currency["USD"] - Decimal("4816.96")) < Decimal("1")
