"""Tests for analytics.performance — TWR, MWR, ROAI."""

from __future__ import annotations

import math
from datetime import date

import pytest

from scrapers.analytics.performance import (
    CashFlow,
    ValuationPoint,
    annualized_return,
    mwr,
    roai,
    twr,
)


class TestTWR:
    def test_no_cashflows_simple_growth(self):
        """Portfolio grows 10% with no deposits/withdrawals."""
        vals = [
            ValuationPoint(date(2024, 1, 1), 10000),
            ValuationPoint(date(2024, 12, 31), 11000),
        ]
        result = twr(vals)
        assert abs(result - 0.10) < 0.001

    def test_with_deposit(self):
        """Deposit should not inflate TWR."""
        vals = [
            ValuationPoint(date(2024, 1, 1), 10000),
            ValuationPoint(date(2024, 7, 1), 15500, cash_flow=5000),  # deposited 5k
            ValuationPoint(date(2024, 12, 31), 16275),
        ]
        result = twr(vals)
        # TWR should reflect only investment performance, not deposits
        # Sub-period 1: (15500 - 5000 - 10000)/10000 = 0.05
        # Sub-period 2: (16275 - 15500)/15500 = 0.05
        # TWR = (1.05)(1.05) - 1 = 0.1025
        assert abs(result - 0.1025) < 0.001

    def test_single_point(self):
        vals = [ValuationPoint(date(2024, 1, 1), 10000)]
        assert twr(vals) == 0.0

    def test_empty(self):
        assert twr([]) == 0.0

    def test_loss(self):
        vals = [
            ValuationPoint(date(2024, 1, 1), 10000),
            ValuationPoint(date(2024, 12, 31), 8500),
        ]
        result = twr(vals)
        assert abs(result - (-0.15)) < 0.001


class TestMWR:
    def test_simple_investment(self):
        """Single investment, no additional cash flows."""
        flows = [
            CashFlow(date(2024, 1, 1), -10000),
            CashFlow(date(2024, 6, 1), 0),  # midpoint marker
        ]
        result = mwr(flows, 11000)
        assert result > 0.05

    def test_multiple_deposits(self):
        """Multiple deposits should produce reasonable IRR."""
        flows = [
            CashFlow(date(2024, 1, 1), -10000),
            CashFlow(date(2024, 6, 1), -5000),
        ]
        result = mwr(flows, 16500)
        assert result > 0.0  # Should be positive

    def test_empty(self):
        assert mwr([], 0) == 0.0


class TestROAI:
    def test_gain(self):
        assert abs(roai(10000, 12000) - 0.20) < 0.001

    def test_loss(self):
        assert abs(roai(10000, 8000) - (-0.20)) < 0.001

    def test_zero_invested(self):
        assert roai(0, 1000) == 0.0


class TestAnnualizedReturn:
    def test_one_year(self):
        result = annualized_return(0.10, 365)
        assert abs(result - 0.10) < 0.01

    def test_two_years(self):
        result = annualized_return(0.21, 730)
        assert abs(result - 0.10) < 0.01

    def test_zero_days(self):
        assert annualized_return(0.10, 0) == 0.0
