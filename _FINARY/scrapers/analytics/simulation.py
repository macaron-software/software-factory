"""Portfolio simulation — compound growth and Monte Carlo.

Implements Finary's "Predict" feature: project future wealth based on
current portfolio, monthly savings, and expected returns.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class SimulationResult:
    """Simulation projection result."""
    years: list[int]
    total_values: list[float]  # total portfolio value each year
    contributions: list[float]  # cumulative contributions
    returns_earned: list[float]  # cumulative investment returns
    final_value: float
    total_contributed: float
    total_return_earned: float
    contribution_rate_pct: float  # % of final value from contributions
    annual_return_used: float


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result with confidence intervals."""
    years: list[int]
    median: list[float]
    p10: list[float]  # 10th percentile (pessimistic)
    p25: list[float]
    p75: list[float]
    p90: list[float]  # 90th percentile (optimistic)
    n_simulations: int


def compound_growth(
    initial_value: float,
    monthly_savings: float,
    annual_return: float = 0.07,
    years: int = 20,
) -> SimulationResult:
    """Deterministic compound growth projection.

    This is Finary's main simulation model:
    V(n) = V(0) * (1+r)^n + PMT * [((1+r)^n - 1) / r]

    where r = monthly rate, n = total months.

    Args:
        initial_value: current portfolio value
        monthly_savings: monthly contribution amount
        annual_return: expected annual return (0.07 = 7%)
        years: projection period

    Returns:
        SimulationResult with year-by-year projections
    """
    monthly_rate = (1 + annual_return) ** (1 / 12) - 1

    year_list = []
    values = []
    contributions_list = []
    returns_list = []

    current = initial_value
    total_contributed = initial_value

    for year in range(1, years + 1):
        for _ in range(12):
            investment_return = current * monthly_rate
            current += investment_return + monthly_savings
            total_contributed += monthly_savings

        returns_earned = current - total_contributed

        year_list.append(year)
        values.append(round(current, 2))
        contributions_list.append(round(total_contributed, 2))
        returns_list.append(round(returns_earned, 2))

    contribution_pct = (total_contributed / current * 100) if current > 0 else 0

    return SimulationResult(
        years=year_list,
        total_values=values,
        contributions=contributions_list,
        returns_earned=returns_list,
        final_value=round(current, 2),
        total_contributed=round(total_contributed, 2),
        total_return_earned=round(current - total_contributed, 2),
        contribution_rate_pct=round(contribution_pct, 1),
        annual_return_used=annual_return,
    )


def monte_carlo(
    initial_value: float,
    monthly_savings: float,
    annual_return: float = 0.07,
    annual_volatility: float = 0.15,
    years: int = 20,
    n_simulations: int = 1000,
    seed: int | None = None,
) -> MonteCarloResult:
    """Monte Carlo simulation with random returns.

    Runs N simulations with normally distributed monthly returns
    to generate confidence intervals.

    Args:
        initial_value: starting portfolio value
        monthly_savings: monthly contribution
        annual_return: expected annual return (mean)
        annual_volatility: annual volatility (std dev)
        years: projection period
        n_simulations: number of simulations
        seed: random seed for reproducibility

    Returns:
        MonteCarloResult with percentile bands
    """
    if seed is not None:
        random.seed(seed)

    monthly_mean = annual_return / 12
    monthly_std = annual_volatility / math.sqrt(12)
    total_months = years * 12

    # Run simulations
    all_results: list[list[float]] = []  # [simulation][year]

    for _ in range(n_simulations):
        current = initial_value
        yearly_values: list[float] = []

        for year in range(years):
            for _ in range(12):
                monthly_return = random.gauss(monthly_mean, monthly_std)
                current = current * (1 + monthly_return) + monthly_savings
                current = max(current, 0)  # floor at zero

            yearly_values.append(current)

        all_results.append(yearly_values)

    # Calculate percentiles
    year_list = list(range(1, years + 1))
    median = []
    p10 = []
    p25 = []
    p75 = []
    p90 = []

    for y in range(years):
        year_values = sorted([sim[y] for sim in all_results])
        n = len(year_values)
        median.append(round(year_values[n // 2], 2))
        p10.append(round(year_values[int(n * 0.10)], 2))
        p25.append(round(year_values[int(n * 0.25)], 2))
        p75.append(round(year_values[int(n * 0.75)], 2))
        p90.append(round(year_values[int(n * 0.90)], 2))

    return MonteCarloResult(
        years=year_list,
        median=median,
        p10=p10,
        p25=p25,
        p75=p75,
        p90=p90,
        n_simulations=n_simulations,
    )
