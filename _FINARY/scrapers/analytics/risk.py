"""Risk analytics — inspired by QuantStats (ranaroussi/quantstats).

Implements: Sharpe, Sortino, max drawdown, volatility, CAGR.
All functions work with daily return series (list of floats).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.03  # 3% EUR risk-free (approximate)


@dataclass
class DrawdownInfo:
    """Drawdown period details."""
    start_idx: int
    end_idx: int
    trough_idx: int
    max_drawdown: float  # negative value (e.g., -0.15 = -15%)
    recovery_days: int | None  # None if not yet recovered


def sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = RISK_FREE_RATE,
    periods: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualized Sharpe Ratio.

    Sharpe = (mean_excess_return) / std(excess_return) * sqrt(periods)

    Args:
        returns: daily returns as decimals (0.01 = +1%)
        risk_free_rate: annualized risk-free rate
        periods: trading days per year (252)

    Returns:
        Annualized Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0

    daily_rf = (1 + risk_free_rate) ** (1 / periods) - 1
    excess = [r - daily_rf for r in returns]

    mean_excess = sum(excess) / len(excess)
    variance = sum((r - mean_excess) ** 2 for r in excess) / (len(excess) - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0

    if std == 0:
        return 0.0

    return (mean_excess / std) * math.sqrt(periods)


def sortino_ratio(
    returns: list[float],
    risk_free_rate: float = RISK_FREE_RATE,
    periods: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualized Sortino Ratio.

    Like Sharpe but only penalizes downside volatility.
    Sortino = mean_excess / downside_deviation * sqrt(periods)

    Args:
        returns: daily returns
        risk_free_rate: annualized risk-free rate
        periods: trading days per year

    Returns:
        Annualized Sortino ratio
    """
    if len(returns) < 2:
        return 0.0

    daily_rf = (1 + risk_free_rate) ** (1 / periods) - 1
    excess = [r - daily_rf for r in returns]

    mean_excess = sum(excess) / len(excess)
    downside = [min(r, 0) ** 2 for r in excess]
    downside_dev = math.sqrt(sum(downside) / len(downside)) if downside else 0.0

    if downside_dev == 0:
        return 0.0

    return (mean_excess / downside_dev) * math.sqrt(periods)


def max_drawdown(values: list[float]) -> DrawdownInfo:
    """Maximum Drawdown from a series of portfolio values (not returns).

    Finds the largest peak-to-trough decline.

    Args:
        values: portfolio values (e.g., [10000, 10500, 9800, ...])

    Returns:
        DrawdownInfo with max drawdown details
    """
    if len(values) < 2:
        return DrawdownInfo(0, 0, 0, 0.0, None)

    peak = values[0]
    peak_idx = 0
    max_dd = 0.0
    dd_start = 0
    dd_trough = 0
    dd_end = 0

    current_dd_start = 0

    for i, v in enumerate(values):
        if v >= peak:
            peak = v
            peak_idx = i
            current_dd_start = i
        else:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
                dd_start = current_dd_start
                dd_trough = i
                dd_end = i

    # Check if recovered
    recovered = False
    recovery_days = None
    if dd_trough < len(values) - 1:
        for i in range(dd_trough + 1, len(values)):
            if values[i] >= values[dd_start]:
                dd_end = i
                recovery_days = i - dd_trough
                recovered = True
                break

    return DrawdownInfo(
        start_idx=dd_start,
        end_idx=dd_end,
        trough_idx=dd_trough,
        max_drawdown=max_dd,
        recovery_days=recovery_days,
    )


def volatility(
    returns: list[float],
    periods: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualized volatility (standard deviation of returns).

    Args:
        returns: daily returns
        periods: trading days per year

    Returns:
        Annualized volatility as decimal
    """
    if len(returns) < 2:
        return 0.0

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(periods)


def cagr(start_value: float, end_value: float, days: int) -> float:
    """Compound Annual Growth Rate.

    Args:
        start_value: initial portfolio value
        end_value: final portfolio value
        days: number of days

    Returns:
        CAGR as decimal (0.12 = 12%/year)
    """
    if start_value <= 0 or end_value <= 0 or days <= 0:
        return 0.0

    years = days / 365.25
    return (end_value / start_value) ** (1 / years) - 1


def values_to_returns(values: list[float]) -> list[float]:
    """Convert portfolio values to daily returns.

    Args:
        values: [10000, 10100, 9950, ...]

    Returns:
        [0.01, -0.0148, ...]
    """
    if len(values) < 2:
        return []
    return [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values)) if values[i - 1] != 0]


def rolling_volatility(
    returns: list[float],
    window: int = 21,
    periods: int = TRADING_DAYS_PER_YEAR,
) -> list[float]:
    """Rolling annualized volatility.

    Args:
        returns: daily returns
        window: rolling window size (21 = ~1 month)
        periods: annualization factor

    Returns:
        List of rolling volatility values
    """
    result = []
    for i in range(window, len(returns) + 1):
        window_returns = returns[i - window:i]
        result.append(volatility(window_returns, periods))
    return result
