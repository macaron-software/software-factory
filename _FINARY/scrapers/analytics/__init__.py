"""Portfolio analytics engine — performance, risk, diversification, simulation."""

from scrapers.analytics.performance import twr, mwr, roai
from scrapers.analytics.risk import sharpe_ratio, sortino_ratio, max_drawdown, volatility, cagr
from scrapers.analytics.diversification import hhi_score, sector_score, geo_score
from scrapers.analytics.fees import compute_fees, projected_savings
from scrapers.analytics.dividends import dividend_yield, project_dividends
from scrapers.analytics.simulation import compound_growth, monte_carlo

__all__ = [
    "twr", "mwr", "roai",
    "sharpe_ratio", "sortino_ratio", "max_drawdown", "volatility", "cagr",
    "hhi_score", "sector_score", "geo_score",
    "compute_fees", "projected_savings",
    "dividend_yield", "project_dividends",
    "compound_growth", "monte_carlo",
]
