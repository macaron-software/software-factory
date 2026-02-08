"""Tests for Trade Republic scraper utilities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scrapers.trade_republic.scraper import _parse_tr_amount, _parse_tr_date


class TestParseTRAmount:
    def test_german_format(self):
        # TR uses German format: 1.234,56
        assert _parse_tr_amount("1.234,56 €") == Decimal("1234.56")

    def test_simple(self):
        assert _parse_tr_amount("23.456,78 €") == Decimal("23456.78")

    def test_no_thousands(self):
        assert _parse_tr_amount("250,00 €") == Decimal("250.00")

    def test_negative(self):
        assert _parse_tr_amount("−45,32 €") == Decimal("-45.32")

    def test_zero(self):
        assert _parse_tr_amount("0,00 €") == Decimal("0.00")


class TestParseTRDate:
    def test_dot_format(self):
        # TR uses DD.MM.YYYY
        assert _parse_tr_date("07.02.2025") == date(2025, 2, 7)

    def test_slash_format(self):
        assert _parse_tr_date("07/02/2025") == date(2025, 2, 7)
