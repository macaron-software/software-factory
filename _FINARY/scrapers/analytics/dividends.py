"""Dividend tracking and projection.

Tracks dividend yield, projects 12-month income, builds monthly distribution calendar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from scrapers.models import Dividend, PortfolioValuation


# Known dividend yields (approximate, annualized)
KNOWN_YIELDS: dict[str, float] = {
    "FR0000120271": 0.0543,  # TotalEnergies
    "FR0000131104": 0.0520,  # BNP Paribas
    "FR0000120644": 0.0310,  # Danone
    "FR0000121014": 0.0380,  # LVMH
    "FR0000120578": 0.0320,  # Sanofi
    "US0378331005": 0.0050,  # Apple
    "US5949181045": 0.0075,  # Microsoft
    "US67066G1040": 0.0000,  # NVIDIA (no dividend)
    "US0231351067": 0.0000,  # Amazon (no dividend)
    "US88160R1014": 0.0000,  # Tesla (no dividend)
}

# Typical dividend months for French stocks (Q1-Q4 payouts)
FRENCH_STOCK_MONTHS = [4, 5, 6]  # Most French companies pay in April-June
US_STOCK_QUARTERS = {
    "AAPL": [2, 5, 8, 11],
    "MSFT": [3, 6, 9, 12],
    "BNP.PA": [5],  # Annual dividend
    "FP.PA": [1, 4, 7, 10],  # TotalEnergies quarterly
}


@dataclass
class DividendSummary:
    """Portfolio-level dividend summary."""
    total_yield: float  # weighted portfolio yield
    projected_annual: float  # projected 12-month income in EUR
    projected_monthly: list[float]  # 12 values, one per month
    positions: list[PositionDividend]
    next_payment: date | None  # next expected dividend date


@dataclass
class PositionDividend:
    """Dividend info for a single position."""
    ticker: str
    name: str
    value_eur: float
    yield_pct: float
    annual_income: float
    frequency: str  # "quarterly", "annual", "monthly"


def dividend_yield(positions: list[PortfolioValuation]) -> DividendSummary:
    """Compute portfolio dividend yield and project income.

    Args:
        positions: valued portfolio positions

    Returns:
        DividendSummary with yield, projections, and per-position breakdown
    """
    total_value = sum(float(p.value_eur) for p in positions) or 1.0
    total_income = 0.0
    monthly: list[float] = [0.0] * 12
    pos_dividends: list[PositionDividend] = []

    for p in positions:
        val = float(p.value_eur)
        isin = p.ticker  # May be ISIN or ticker

        # Look up yield
        yld = KNOWN_YIELDS.get(isin, 0.0)

        # For stocks without known yield, estimate from asset type
        if yld == 0 and p.asset_type.value == "stock" and p.country == "FR":
            yld = 0.03  # ~3% average for French stocks
        elif yld == 0 and p.asset_type.value == "etf":
            yld = 0.02  # ~2% for broad market ETFs

        annual_income = val * yld
        total_income += annual_income

        # Distribute across months
        ticker_key = p.ticker.split(".")[0] if "." in p.ticker else p.ticker
        months = US_STOCK_QUARTERS.get(ticker_key)
        if months:
            per_payment = annual_income / len(months)
            frequency = "quarterly" if len(months) == 4 else "annual"
            for m in months:
                monthly[m - 1] += per_payment
        elif p.country == "FR":
            # French companies typically pay in May
            monthly[4] += annual_income
            frequency = "annual"
        else:
            # Default: distribute quarterly
            per_q = annual_income / 4
            for m in [2, 5, 8, 11]:
                monthly[m] += per_q
            frequency = "quarterly"

        if yld > 0:
            pos_dividends.append(PositionDividend(
                ticker=p.ticker,
                name=p.name,
                value_eur=val,
                yield_pct=round(yld * 100, 2),
                annual_income=round(annual_income, 2),
                frequency=frequency,
            ))

    weighted_yield = total_income / total_value if total_value > 0 else 0.0

    # Find next payment date
    today = date.today()
    next_payment = None
    for i in range(12):
        month_idx = (today.month - 1 + i) % 12
        if monthly[month_idx] > 0:
            year = today.year + ((today.month + i - 1) // 12)
            next_payment = date(year, month_idx + 1, 15)
            if next_payment > today:
                break

    return DividendSummary(
        total_yield=round(weighted_yield * 100, 2),
        projected_annual=round(total_income, 2),
        projected_monthly=[round(m, 2) for m in monthly],
        positions=sorted(pos_dividends, key=lambda d: -d.annual_income),
        next_payment=next_payment,
    )


def project_dividends(
    positions: list[PortfolioValuation],
    history: list[Dividend],
    growth_rate: float = 0.03,
    years: int = 5,
) -> list[float]:
    """Project dividend income over N years with growth rate.

    Args:
        positions: current positions
        history: past dividend payments
        growth_rate: expected annual dividend growth (3% default)
        years: projection horizon

    Returns:
        List of projected annual income for each year
    """
    summary = dividend_yield(positions)
    base = summary.projected_annual

    return [round(base * (1 + growth_rate) ** y, 2) for y in range(years)]
