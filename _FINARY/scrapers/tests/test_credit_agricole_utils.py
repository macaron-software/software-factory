"""Tests for Crédit Agricole scraper utilities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scrapers.credit_agricole.scraper import _detect_ca_type, get_region_for_department
from scrapers.models import AccountType


class TestDetectCAType:
    def test_savings(self):
        assert _detect_ca_type("Livret A") == AccountType.SAVINGS
        assert _detect_ca_type("LDD Solidaire") == AccountType.SAVINGS

    def test_loan(self):
        assert _detect_ca_type("Prêt Immobilier") == AccountType.LOAN
        assert _detect_ca_type("Crédit Consommation") == AccountType.LOAN

    def test_checking(self):
        assert _detect_ca_type("Compte de dépôt") == AccountType.CHECKING

    def test_pea(self):
        assert _detect_ca_type("PEA Actions") == AccountType.PEA

    def test_av(self):
        assert _detect_ca_type("Assurance Vie") == AccountType.AV


class TestRegionMapping:
    def test_paris(self):
        assert get_region_for_department(75) == "ca-paris"

    def test_lyon(self):
        assert get_region_for_department(69) == "ca-centrest"

    def test_normandie(self):
        assert get_region_for_department(14) == "ca-normandie"

    def test_unknown_defaults_paris(self):
        assert get_region_for_department(999) == "ca-paris"
