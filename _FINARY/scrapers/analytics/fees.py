"""Fee scanner — detect and project investment fees.

Inspired by Finary's fee scanner feature.
Detects: TER (Total Expense Ratio) for ETFs/funds, transaction fees, custody fees.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from scrapers.models import PortfolioValuation


# Common ETF TERs (Total Expense Ratio) — well-known funds
KNOWN_TERS: dict[str, float] = {
    # Vanguard
    "IE00BK5BQT80": 0.0022,  # VWCE - Vanguard FTSE All-World
    "IE00B3RBWM25": 0.0012,  # VWRL - Vanguard FTSE All-World Dist
    "IE00B3XXRP09": 0.0007,  # Vanguard S&P 500
    "IE00BFMXXD54": 0.0007,  # Vanguard S&P 500 ACC
    # iShares
    "IE00B5BMR087": 0.0007,  # iShares Core S&P 500
    "IE00B4L5Y983": 0.0020,  # iShares Core MSCI World
    "IE00B1XNHC34": 0.0030,  # iShares MSCI EM
    # Amundi
    "LU1681043599": 0.0015,  # Amundi MSCI World
    "LU1681048804": 0.0015,  # Amundi S&P 500
    "LU1437016972": 0.0005,  # Amundi Prime Global
    # BNP
    "FR0011550185": 0.0015,  # BNP Easy S&P 500
    # Lyxor
    "FR0010315770": 0.0025,  # Lyxor MSCI World
}

# Default TER by asset type
DEFAULT_TERS = {
    "etf": 0.0020,
    "fund": 0.0150,  # active funds typically 1-2%
    "stock": 0.0,
    "bond": 0.0,
    "crypto": 0.0,
    "option": 0.0,
}

# Typical broker transaction fees
BROKER_FEES = {
    "ibkr": {"per_trade": 1.0, "custody_pct": 0.0},
    "trade_republic": {"per_trade": 1.0, "custody_pct": 0.0},
    "boursobank": {"per_trade": 1.99, "custody_pct": 0.0},  # Bourso Discover
    "credit_agricole": {"per_trade": 5.0, "custody_pct": 0.002},
}


@dataclass
class FeeAnalysis:
    """Fee analysis for a single position."""
    ticker: str
    name: str
    value_eur: float
    ter: float  # annual TER as decimal (0.0022 = 0.22%)
    annual_fee_eur: float  # TER * value
    source: str  # "known", "default", "manual"


@dataclass
class PortfolioFees:
    """Aggregated fee analysis for the portfolio."""
    total_value: float
    total_annual_fees: float
    weighted_ter: float  # weighted average TER
    positions: list[FeeAnalysis]
    potential_savings: float  # vs switching to cheapest ETFs
    savings_description: str


def compute_fees(positions: list[PortfolioValuation]) -> PortfolioFees:
    """Analyze fees across all portfolio positions.

    Args:
        positions: valued portfolio positions

    Returns:
        PortfolioFees with per-position and aggregate analysis
    """
    analyses: list[FeeAnalysis] = []
    total_value = 0.0
    total_fees = 0.0

    for p in positions:
        val = float(p.value_eur)
        total_value += val

        # Look up TER
        ter = 0.0
        source = "default"

        if p.ticker in KNOWN_TERS:
            ter = KNOWN_TERS[p.ticker]
            source = "known"
        elif hasattr(p, 'isin') and p.ticker:
            # Try ISIN lookup
            for isin, t in KNOWN_TERS.items():
                if isin == p.ticker:
                    ter = t
                    source = "known"
                    break

        if source == "default":
            ter = DEFAULT_TERS.get(p.asset_type.value, 0.0)

        fee = val * ter
        total_fees += fee

        analyses.append(FeeAnalysis(
            ticker=p.ticker,
            name=p.name,
            value_eur=val,
            ter=ter,
            annual_fee_eur=round(fee, 2),
            source=source,
        ))

    weighted_ter = total_fees / total_value if total_value > 0 else 0.0

    # Calculate potential savings (compare to cheapest equivalent ETFs)
    potential_savings = 0.0
    cheapest_ter = 0.0005  # Amundi Prime Global TER
    for a in analyses:
        if a.ter > cheapest_ter and a.ter > 0:
            savings = a.value_eur * (a.ter - cheapest_ter)
            potential_savings += savings

    return PortfolioFees(
        total_value=round(total_value, 2),
        total_annual_fees=round(total_fees, 2),
        weighted_ter=round(weighted_ter, 6),
        positions=sorted(analyses, key=lambda a: -a.annual_fee_eur),
        potential_savings=round(potential_savings, 2),
        savings_description=f"En passant aux ETFs les moins chers, vous pourriez economiser {potential_savings:.0f} EUR/an",
    )


def projected_savings(current_fees: float, optimal_fees: float, years: int = 10) -> float:
    """Project cumulative savings over N years from fee reduction.

    Accounts for compound effect of lower fees on returns.

    Args:
        current_fees: current annual fee rate (e.g., 0.015 = 1.5%)
        optimal_fees: target annual fee rate (e.g., 0.002 = 0.2%)
        years: projection horizon

    Returns:
        Cumulative savings in EUR for a 100k portfolio
    """
    portfolio = 100_000
    annual_return = 0.07  # 7% annual return assumption

    value_current = portfolio
    value_optimal = portfolio

    for _ in range(years):
        value_current *= (1 + annual_return - current_fees)
        value_optimal *= (1 + annual_return - optimal_fees)

    return round(value_optimal - value_current, 2)
