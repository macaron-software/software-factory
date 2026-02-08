"""Portfolio performance calculators.

Implements TWR, MWR (IRR), and ROAI — inspired by Ghostfolio's calculator engine.
Reference: ghostfolio/ghostfolio apps/api/src/app/portfolio/calculator/
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class CashFlow:
    """A cash flow event (deposit, withdrawal, dividend)."""
    date: date
    amount: float  # positive = inflow, negative = outflow


@dataclass
class ValuationPoint:
    """Portfolio value at a point in time."""
    date: date
    value: float
    cash_flow: float = 0.0  # net cash flow on this day


def twr(valuations: list[ValuationPoint]) -> float:
    """Time-Weighted Return (TWR).

    Eliminates the impact of cash flows to measure pure investment performance.
    Used by Finary, Ghostfolio, and most institutional benchmarks.

    Algorithm:
        1. Split into sub-periods at each cash flow event
        2. For each sub-period: HPR = (V_end - V_start - CF) / V_start
        3. TWR = product of (1 + HPR_i) - 1

    Args:
        valuations: chronologically sorted list of ValuationPoint

    Returns:
        TWR as a decimal (0.15 = 15% return)
    """
    if len(valuations) < 2:
        return 0.0

    product = 1.0

    for i in range(1, len(valuations)):
        v_start = valuations[i - 1].value
        v_end = valuations[i].value
        cf = valuations[i].cash_flow

        if v_start == 0:
            continue

        # Holding Period Return
        hpr = (v_end - cf - v_start) / v_start if v_start != 0 else 0.0
        product *= (1 + hpr)

    return product - 1


def mwr(cash_flows: list[CashFlow], final_value: float, tolerance: float = 1e-8, max_iter: int = 1000) -> float:
    """Money-Weighted Return (MWR) — also known as IRR.

    Accounts for the timing and size of cash flows.
    Solved via Newton-Raphson on the NPV equation.

    Args:
        cash_flows: list of CashFlow (first should be initial investment as negative)
        final_value: current portfolio value
        tolerance: convergence threshold
        max_iter: max Newton-Raphson iterations

    Returns:
        Annualized IRR as decimal (0.12 = 12%/year)
    """
    if not cash_flows or final_value <= 0:
        return 0.0

    base_date = cash_flows[0].date

    # Build time-value pairs: [(years_from_start, amount)]
    flows: list[tuple[float, float]] = []
    for cf in cash_flows:
        t = (cf.date - base_date).days / 365.25
        flows.append((t, cf.amount))

    # Final value as last positive cash flow
    last_date = max(cf.date for cf in cash_flows)
    t_final = max((last_date - base_date).days / 365.25, flows[-1][0] + 1 / 365.25)
    flows.append((t_final, final_value))

    # Newton-Raphson to find r where NPV(r) = 0
    r = 0.1  # initial guess

    for _ in range(max_iter):
        npv = 0.0
        d_npv = 0.0

        for t, amount in flows:
            factor = (1 + r) ** t
            if factor == 0:
                continue
            npv += amount / factor
            if t != 0:
                d_npv -= t * amount / ((1 + r) ** (t + 1))

        if abs(d_npv) < 1e-15:
            break

        r_new = r - npv / d_npv

        if abs(r_new - r) < tolerance:
            return r_new

        r = r_new

    return r


def roai(invested: float, current_value: float) -> float:
    """Return on Average Investment (ROAI).

    Simple metric: (current - invested) / invested.
    Used when cash flow timing data is unavailable.

    Args:
        invested: total amount invested
        current_value: current portfolio value

    Returns:
        ROAI as decimal (0.25 = 25%)
    """
    if invested == 0:
        return 0.0
    return (current_value - invested) / invested


def annualized_return(total_return: float, days: int) -> float:
    """Convert a total return over N days to annualized return.

    Args:
        total_return: total return as decimal (0.15 = 15%)
        days: number of days

    Returns:
        Annualized return as decimal
    """
    if days <= 0 or total_return <= -1:
        return 0.0
    years = days / 365.25
    if years < 1 / 365.25:
        return total_return
    return (1 + total_return) ** (1 / years) - 1
