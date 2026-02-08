"""Tests for Boursobank scraper amount/date parsing utilities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scrapers.boursobank.scraper import _detect_account_type, _parse_amount, _parse_date
from scrapers.models import AccountType


class TestParseAmount:
    def test_simple(self):
        assert _parse_amount("1234.56") == Decimal("1234.56")

    def test_french_format(self):
        assert _parse_amount("1 234,56 €") == Decimal("1234.56")

    def test_negative(self):
        assert _parse_amount("-45,32 €") == Decimal("-45.32")

    def test_negative_with_unicode_minus(self):
        assert _parse_amount("−1 250,00 €") == Decimal("-1250.00")

    def test_narrow_nbsp(self):
        # \u202f is narrow no-break space, used in French
        assert _parse_amount("22\u202f950,00\u202f€") == Decimal("22950.00")

    def test_zero(self):
        assert _parse_amount("0,00 €") == Decimal("0.00")

    def test_empty(self):
        assert _parse_amount("") == Decimal("0")

    def test_garbage(self):
        assert _parse_amount("not a number") == Decimal("0")


class TestParseDate:
    def test_slash_format(self):
        assert _parse_date("08/02/2025") == date(2025, 2, 8)

    def test_dash_format(self):
        assert _parse_date("08-02-2025") == date(2025, 2, 8)

    def test_fallback(self):
        # Unknown format returns today
        result = _parse_date("xyz")
        assert isinstance(result, date)


class TestDetectAccountType:
    def test_pea(self):
        assert _detect_account_type("PEA", "Mon PEA") == AccountType.PEA

    def test_cto(self):
        assert _detect_account_type("", "Compte Titres") == AccountType.CTO

    def test_savings(self):
        assert _detect_account_type("", "Livret A") == AccountType.SAVINGS
        assert _detect_account_type("", "LDD Solidaire") == AccountType.SAVINGS

    def test_av(self):
        assert _detect_account_type("Assurance Vie", "") == AccountType.AV

    def test_loan(self):
        assert _detect_account_type("", "Prêt Immobilier") == AccountType.LOAN

    def test_default_checking(self):
        assert _detect_account_type("", "Compte Courant") == AccountType.CHECKING
