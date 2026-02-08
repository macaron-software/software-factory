"""Transaction categorizer — regex rules + category detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Default categorization rules (French merchants)
DEFAULT_RULES: list[tuple[str, str, int]] = [
    (r"CARREFOUR|LECLERC|AUCHAN|LIDL|MONOPRIX|FRANPRIX|PICARD|CASINO|INTERMARCHE|SUPER U", "alimentation", 10),
    (r"UBER EATS|DELIVEROO|JUST EAT|DOMINOS|MCDONALDS|BURGER KING|KFC|STARBUCKS|FIVE GUYS", "restauration", 10),
    (r"BOULANGERIE|PATISSERIE|PAUL |BRIOCHE DOREE", "restauration", 8),
    (r"SNCF|RATP|UBER |BOLT |LIME |BLABLACAR|TIER ", "transport", 10),
    (r"TOTAL ENERGIES|SHELL |BP |ESSO |STATION SERVICE", "transport", 8),
    (r"NETFLIX|SPOTIFY|DISNEY|CANAL\+|AMAZON PRIME|APPLE\.COM|DEEZER|OCS|YOUTUBE|CRUNCHYROLL", "abonnements", 10),
    (r"SFR|ORANGE|FREE MOBILE|BOUYGUES TEL", "telecom", 10),
    (r"LOYER|RENT|FONCIA|NEXITY|ORPI|CENTURY 21|SELOGER", "logement", 10),
    (r"EDF|ENGIE|VEOLIA|SUEZ|GAZ DE FRANCE|ENEDIS", "energie", 10),
    (r"AXA|MAIF|MACIF|MATMUT|ALLIANZ|GENERALI|MMA|GROUPAMA", "assurance", 10),
    (r"PHARMACIE|DOCTOLIB|AMELI|CPAM|MUTUELLE|MEDICAL", "sante", 10),
    (r"FNAC|DARTY|AMAZON|CDISCOUNT|ZALANDO|ZARA|H&M|DECATHLON|IKEA|LEROY MERLIN", "shopping", 10),
    (r"SALAIRE|(?<!\w)PAIE(?!\w)|VIR\b.*EMPL|TRAITEMENT", "revenus", 20),
    (r"ALLOC|CAF|POLE EMPLOI|FRANCE TRAVAIL", "aides", 15),
    (r"IMPOTS|TRESOR PUBLIC|DGFIP|TAXE", "impots", 15),
    (r"VIREMENT.*EPARGNE|VIR.*LIVRET|VIR.*PEA", "epargne", 5),
    (r"APPLE STORE|GOOGLE PLAY", "tech", 8),
    (r"BANQUE|FRAIS|COMMISSION|COTISATION CARTE", "frais_bancaires", 10),
    (r"RETRAIT DAB|RETRAIT GAB", "retrait", 10),
]


@dataclass
class CategoryRule:
    pattern: re.Pattern
    category: str
    priority: int


class TransactionCategorizer:
    """Categorizes bank transactions using regex rules."""

    def __init__(self, extra_rules: list[tuple[str, str, int]] | None = None) -> None:
        self.rules: list[CategoryRule] = []
        all_rules = DEFAULT_RULES + (extra_rules or [])
        for pattern, category, priority in all_rules:
            self.rules.append(
                CategoryRule(
                    pattern=re.compile(pattern, re.IGNORECASE),
                    category=category,
                    priority=priority,
                )
            )
        # Sort by priority descending (highest priority matched first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def categorize(self, description: str) -> str | None:
        """Return category for a transaction description, or None if no match."""
        for rule in self.rules:
            if rule.pattern.search(description):
                return rule.category
        return None

    def categorize_batch(self, descriptions: list[str]) -> list[str | None]:
        """Categorize multiple descriptions."""
        return [self.categorize(d) for d in descriptions]
