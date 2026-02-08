"""Tests for Crédit Agricole scraper utilities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scrapers.credit_agricole.scraper import _detect_ca_type, _parse_ca_amount, _parse_ca_date
from scrapers.models import AccountType


class TestParseCAAmount:
    def test_simple(self):
        assert _parse_ca_amount("1234,56 €") == Decimal("1234.56")

    def test_negative(self):
        assert _parse_ca_amount("-185 000,00 €") == Decimal("-185000.00")

    def test_unicode_minus(self):
        assert _parse_ca_amount("−1 350,00 €") == Decimal("-1350.00")

    def test_no_space(self):
        assert _parse_ca_amount("3210,45€") == Decimal("3210.45")


class TestParseCADate:
    def test_standard(self):
        assert _parse_ca_date("06/02/2025") == date(2025, 2, 6)

    def test_short_year(self):
        assert _parse_ca_date("06/02/25") == date(2025, 2, 6)


class TestDetectCAType:
    def test_savings(self):
        assert _detect_ca_type("Livret A") == AccountType.SAVINGS
        assert _detect_ca_type("LDD Solidaire") == AccountType.SAVINGS

    def test_loan(self):
        assert _detect_ca_type("Prêt Immobilier") == AccountType.LOAN
        assert _detect_ca_type("Crédit Consommation") == AccountType.LOAN

    def test_checking(self):
        assert _detect_ca_type("Compte de dépôt") == AccountType.CHECKING
