"""Tests for the transaction categorizer."""

from __future__ import annotations

import pytest

from scrapers.categorizer import TransactionCategorizer


@pytest.fixture
def categorizer():
    return TransactionCategorizer()


class TestCategorizerBasic:
    def test_supermarket(self, categorizer):
        assert categorizer.categorize("CARTE CARREFOUR CITY PARIS") == "alimentation"
        assert categorizer.categorize("CARTE LECLERC DRIVE") == "alimentation"
        assert categorizer.categorize("CARTE LIDL 1234") == "alimentation"
        assert categorizer.categorize("CB MONOPRIX PARIS 15") == "alimentation"

    def test_restaurants(self, categorizer):
        assert categorizer.categorize("CARTE UBER EATS") == "restauration"
        assert categorizer.categorize("DELIVEROO *ORDER") == "restauration"
        assert categorizer.categorize("CARTE MCDONALDS PARIS") == "restauration"

    def test_transport(self, categorizer):
        assert categorizer.categorize("CARTE SNCF VOYAGE") == "transport"
        assert categorizer.categorize("RATP NAVIGO") == "transport"
        assert categorizer.categorize("UBER TRIP 12345") == "transport"
        assert categorizer.categorize("TOTAL ENERGIES STATION") == "transport"

    def test_subscriptions(self, categorizer):
        assert categorizer.categorize("PRLV NETFLIX") == "abonnements"
        assert categorizer.categorize("PRLV SPOTIFY PREMIUM") == "abonnements"
        assert categorizer.categorize("DISNEY+ SUBSCRIPTION") == "abonnements"
        assert categorizer.categorize("APPLE.COM/BILL") == "abonnements"

    def test_telecom(self, categorizer):
        assert categorizer.categorize("PRLV SFR MOBILE") == "telecom"
        assert categorizer.categorize("PRLV FREE MOBILE") == "telecom"
        assert categorizer.categorize("ORANGE SA FACTURE") == "telecom"

    def test_housing(self, categorizer):
        assert categorizer.categorize("PRLV LOYER FONCIA") == "logement"
        assert categorizer.categorize("VIR RENT APPARTEMENT") == "logement"

    def test_energy(self, categorizer):
        assert categorizer.categorize("PRLV EDF ELECTRICITE") == "energie"
        assert categorizer.categorize("PRLV ENGIE GAZ") == "energie"

    def test_insurance(self, categorizer):
        assert categorizer.categorize("PRLV MACIF ASSURANCE AUTO") == "assurance"
        assert categorizer.categorize("AXA PREVOYANCE") == "assurance"

    def test_health(self, categorizer):
        assert categorizer.categorize("CARTE PHARMACIE DU CENTRE") == "sante"
        assert categorizer.categorize("DOCTOLIB CONSULTATION") == "sante"

    def test_shopping(self, categorizer):
        assert categorizer.categorize("CARTE FNAC.COM") == "shopping"
        assert categorizer.categorize("AMAZON EU SARL") == "shopping"
        assert categorizer.categorize("CARTE DECATHLON PARIS") == "shopping"
        assert categorizer.categorize("CARTE IKEA FRANCE") == "shopping"

    def test_income(self, categorizer):
        assert categorizer.categorize("VIR SALAIRE MACARON SOFTWARE") == "revenus"
        assert categorizer.categorize("VIREMENT PAIE JANVIER") == "revenus"

    def test_taxes(self, categorizer):
        assert categorizer.categorize("PRLV TRESOR PUBLIC IMPOT") == "impots"
        assert categorizer.categorize("DGFIP IMPOTS REVENUS") == "impots"

    def test_savings(self, categorizer):
        assert categorizer.categorize("VIREMENT EPARGNE LIVRET") == "epargne"
        assert categorizer.categorize("VIR VERS PEA BOURSO") == "epargne"

    def test_bank_fees(self, categorizer):
        assert categorizer.categorize("FRAIS BANCAIRES TRIMESTRIELS") == "frais_bancaires"
        assert categorizer.categorize("COTISATION CARTE VISA") == "frais_bancaires"

    def test_unknown_returns_none(self, categorizer):
        assert categorizer.categorize("XYZ RANDOM MERCHANT 12345") is None
        assert categorizer.categorize("PAIEMENT CB 98765") is None


class TestCategorizerBatch:
    def test_batch(self, categorizer):
        descriptions = [
            "CARTE CARREFOUR",
            "VIR SALAIRE",
            "UNKNOWN MERCHANT",
            "PRLV NETFLIX",
        ]
        results = categorizer.categorize_batch(descriptions)
        assert results == ["alimentation", "revenus", None, "abonnements"]


class TestCategorizerCustomRules:
    def test_extra_rules(self):
        extra = [("OVH|SCALEWAY|HETZNER", "infra_cloud", 10)]
        cat = TransactionCategorizer(extra_rules=extra)
        assert cat.categorize("CARTE OVH CLOUD") == "infra_cloud"
        assert cat.categorize("SCALEWAY SAS") == "infra_cloud"
        # Default rules still work
        assert cat.categorize("CARTE CARREFOUR") == "alimentation"
