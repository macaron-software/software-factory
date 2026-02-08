"""Diversification scoring — sector and geographic concentration analysis.

Uses Herfindahl-Hirschman Index (HHI) to measure concentration.
Inspired by PyPortfolioOpt and Finary's 1-10 diversification gauge.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from scrapers.models import PortfolioValuation


@dataclass
class DiversificationResult:
    """Diversification analysis result."""
    score: int  # 1-10 (1 = very concentrated, 10 = well diversified)
    hhi: float  # 0-10000 (0 = perfect, 10000 = single holding)
    label: str  # "Insufficient", "Low", "Moderate", "Good", "Excellent"
    breakdown: dict[str, float]  # {category: weight%}
    top_concentration: str  # name of largest category
    top_weight: float  # weight of largest category


# Ideal sector allocation (rough S&P 500 weights)
IDEAL_SECTORS = {
    "Technology": 0.28,
    "Healthcare": 0.13,
    "Financials": 0.13,
    "Consumer Discretionary": 0.10,
    "Communication Services": 0.09,
    "Industrials": 0.09,
    "Consumer Staples": 0.06,
    "Energy": 0.05,
    "Utilities": 0.03,
    "Real Estate": 0.02,
    "Materials": 0.02,
}

# Major geographic regions
REGION_MAP = {
    "US": "Amerique du Nord",
    "CA": "Amerique du Nord",
    "FR": "Europe",
    "DE": "Europe",
    "GB": "Europe",
    "NL": "Europe",
    "IE": "Europe",
    "CH": "Europe",
    "ES": "Europe",
    "IT": "Europe",
    "BE": "Europe",
    "LU": "Europe",
    "AT": "Europe",
    "PT": "Europe",
    "SE": "Europe",
    "DK": "Europe",
    "NO": "Europe",
    "FI": "Europe",
    "JP": "Asie-Pacifique",
    "CN": "Asie-Pacifique",
    "HK": "Asie-Pacifique",
    "KR": "Asie-Pacifique",
    "TW": "Asie-Pacifique",
    "AU": "Asie-Pacifique",
    "SG": "Asie-Pacifique",
    "IN": "Asie-Pacifique",
    "BR": "Amerique Latine",
    "MX": "Amerique Latine",
}


def hhi_score(weights: list[float]) -> float:
    """Herfindahl-Hirschman Index.

    HHI = sum(w_i^2) where w_i is weight as percentage (0-100).
    Range: 1/N * 10000 (equally distributed) to 10000 (single holding).

    Args:
        weights: portfolio weights as fractions (0.0-1.0), must sum to ~1.0

    Returns:
        HHI value (0-10000)
    """
    if not weights:
        return 10000.0
    return sum((w * 100) ** 2 for w in weights)


def _hhi_to_score(hhi: float, n_categories: int) -> tuple[int, str]:
    """Convert HHI to a 1-10 diversification score.

    Based on typical thresholds:
    - HHI < 1500: well diversified (score 7-10)
    - HHI 1500-2500: moderate (score 4-6)
    - HHI > 2500: concentrated (score 1-3)
    """
    if n_categories <= 1:
        return 1, "Insuffisant"

    if hhi < 800:
        return 10, "Excellent"
    elif hhi < 1200:
        return 9, "Excellent"
    elif hhi < 1500:
        return 8, "Bon"
    elif hhi < 1800:
        return 7, "Bon"
    elif hhi < 2200:
        return 6, "Moderé"
    elif hhi < 2500:
        return 5, "Moderé"
    elif hhi < 3500:
        return 4, "Faible"
    elif hhi < 5000:
        return 3, "Faible"
    elif hhi < 7500:
        return 2, "Insuffisant"
    else:
        return 1, "Insuffisant"


def sector_score(positions: list[PortfolioValuation]) -> DiversificationResult:
    """Compute sector diversification score.

    Args:
        positions: valued portfolio positions

    Returns:
        DiversificationResult with sector breakdown
    """
    if not positions:
        return DiversificationResult(1, 10000, "Insuffisant", {}, "N/A", 0.0)

    total = sum(float(p.value_eur) for p in positions)
    if total <= 0:
        return DiversificationResult(1, 10000, "Insuffisant", {}, "N/A", 0.0)

    sector_weights: dict[str, float] = {}
    for p in positions:
        sector = p.sector or "Non classé"
        weight = float(p.value_eur) / total
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

    weights = list(sector_weights.values())
    hhi = hhi_score(weights)
    score, label = _hhi_to_score(hhi, len(sector_weights))

    top = max(sector_weights, key=sector_weights.get)  # type: ignore

    return DiversificationResult(
        score=score,
        hhi=hhi,
        label=label,
        breakdown={k: round(v * 100, 1) for k, v in sorted(sector_weights.items(), key=lambda x: -x[1])},
        top_concentration=top,
        top_weight=round(sector_weights[top] * 100, 1),
    )


def geo_score(positions: list[PortfolioValuation]) -> DiversificationResult:
    """Compute geographic diversification score.

    Args:
        positions: valued portfolio positions

    Returns:
        DiversificationResult with geographic breakdown
    """
    if not positions:
        return DiversificationResult(1, 10000, "Insuffisant", {}, "N/A", 0.0)

    total = sum(float(p.value_eur) for p in positions)
    if total <= 0:
        return DiversificationResult(1, 10000, "Insuffisant", {}, "N/A", 0.0)

    region_weights: dict[str, float] = {}
    for p in positions:
        country = p.country or "XX"
        region = REGION_MAP.get(country, "Autre")
        weight = float(p.value_eur) / total
        region_weights[region] = region_weights.get(region, 0.0) + weight

    weights = list(region_weights.values())
    hhi = hhi_score(weights)
    score, label = _hhi_to_score(hhi, len(region_weights))

    top = max(region_weights, key=region_weights.get)  # type: ignore

    return DiversificationResult(
        score=score,
        hhi=hhi,
        label=label,
        breakdown={k: round(v * 100, 1) for k, v in sorted(region_weights.items(), key=lambda x: -x[1])},
        top_concentration=top,
        top_weight=round(region_weights[top] * 100, 1),
    )


def asset_class_breakdown(positions: list[PortfolioValuation]) -> dict[str, float]:
    """Breakdown by asset class (stocks, ETFs, bonds, crypto, etc.)."""
    if not positions:
        return {}

    total = sum(float(p.value_eur) for p in positions)
    if total <= 0:
        return {}

    breakdown: dict[str, float] = {}
    for p in positions:
        cls = p.asset_type.value
        weight = float(p.value_eur) / total
        breakdown[cls] = breakdown.get(cls, 0.0) + weight

    return {k: round(v * 100, 1) for k, v in sorted(breakdown.items(), key=lambda x: -x[1])}
