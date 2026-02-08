"""Tests for analytics.risk — Sharpe, Sortino, drawdown, volatility."""

from __future__ import annotations

import math

import pytest

from scrapers.analytics.risk import (
    cagr,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    values_to_returns,
    volatility,
)


class TestSharpeRatio:
    def test_positive_returns(self):
        # Varying positive returns averaging ~0.05%/day
        import random
        random.seed(42)
        returns = [0.0005 + random.gauss(0, 0.005) for _ in range(252)]
        result = sharpe_ratio(returns, risk_free_rate=0.03)
        assert isinstance(result, float)

    def test_negative_mean(self):
        # Returns below risk-free → negative Sharpe
        import random
        random.seed(42)
        returns = [-0.001 + random.gauss(0, 0.005) for _ in range(252)]
        result = sharpe_ratio(returns, risk_free_rate=0.03)
        assert result < 0

    def test_single_return(self):
        assert sharpe_ratio([0.01]) == 0.0

    def test_empty(self):
        assert sharpe_ratio([]) == 0.0


class TestSortinoRatio:
    def test_positive_only(self):
        returns = [0.001] * 252
        result = sortino_ratio(returns, risk_free_rate=0.03)
        # All positive → no downside deviation → very high or inf
        # With daily_rf subtracted, some will be "negative" excess
        assert isinstance(result, float)

    def test_mixed_returns(self):
        returns = [0.01, -0.02, 0.015, -0.005, 0.008] * 50
        result = sortino_ratio(returns)
        assert isinstance(result, float)


class TestMaxDrawdown:
    def test_simple_drawdown(self):
        values = [100, 110, 105, 90, 95, 100, 115]
        dd = max_drawdown(values)
        # Peak at 110, trough at 90 → -18.18%
        assert abs(dd.max_drawdown - (-20 / 110)) < 0.01
        assert dd.trough_idx == 3

    def test_no_drawdown(self):
        values = [100, 110, 120, 130]
        dd = max_drawdown(values)
        assert dd.max_drawdown == 0.0

    def test_single_value(self):
        dd = max_drawdown([100])
        assert dd.max_drawdown == 0.0

    def test_recovery(self):
        values = [100, 80, 90, 110]
        dd = max_drawdown(values)
        assert dd.max_drawdown < 0
        assert dd.recovery_days is not None


class TestVolatility:
    def test_constant_returns(self):
        returns = [0.001] * 100
        assert volatility(returns) < 0.001

    def test_volatile_returns(self):
        returns = [0.02, -0.02] * 100
        vol = volatility(returns)
        assert vol > 0.20  # should be high

    def test_empty(self):
        assert volatility([]) == 0.0


class TestCAGR:
    def test_basic(self):
        # 10000 → 20000 in 7 years ≈ 10.4% CAGR
        result = cagr(10000, 20000, 7 * 365)
        assert 0.09 < result < 0.12

    def test_one_year(self):
        result = cagr(10000, 11000, 365)
        assert abs(result - 0.10) < 0.02

    def test_zero_start(self):
        assert cagr(0, 10000, 365) == 0.0


class TestValuesToReturns:
    def test_basic(self):
        values = [100, 110, 105]
        returns = values_to_returns(values)
        assert len(returns) == 2
        assert abs(returns[0] - 0.10) < 0.001
        assert abs(returns[1] - (-0.04545)) < 0.001

    def test_empty(self):
        assert values_to_returns([]) == []
        assert values_to_returns([100]) == []
