"""Tests for analytics.simulation — compound growth and Monte Carlo."""

from __future__ import annotations

import pytest

from scrapers.analytics.simulation import compound_growth, monte_carlo


class TestCompoundGrowth:
    def test_basic_projection(self):
        result = compound_growth(
            initial_value=10000,
            monthly_savings=250,
            annual_return=0.07,
            years=20,
        )
        assert len(result.years) == 20
        assert result.final_value > 10000 + (250 * 12 * 20)  # must beat inflation
        assert result.total_contributed == 10000 + (250 * 12 * 20)
        assert result.total_return_earned > 0
        assert result.contribution_rate_pct > 0

    def test_no_savings(self):
        result = compound_growth(10000, 0, 0.07, 10)
        assert len(result.years) == 10
        # Pure compound: 10000 * 1.07^10 ≈ 19671
        assert 19000 < result.final_value < 20500

    def test_no_return(self):
        result = compound_growth(0, 500, 0.0, 10)
        # Just savings: 500 * 12 * 10 = 60000
        assert abs(result.final_value - 60000) < 1

    def test_years_progression(self):
        result = compound_growth(10000, 100, 0.07, 5)
        # Each year should be larger than the previous
        for i in range(1, len(result.total_values)):
            assert result.total_values[i] > result.total_values[i - 1]


class TestMonteCarlo:
    def test_basic_simulation(self):
        result = monte_carlo(
            initial_value=10000,
            monthly_savings=250,
            annual_return=0.07,
            annual_volatility=0.15,
            years=10,
            n_simulations=500,
            seed=42,
        )
        assert len(result.years) == 10
        assert len(result.median) == 10
        assert result.n_simulations == 500

        # Percentiles should be ordered: p10 < p25 < median < p75 < p90
        for i in range(10):
            assert result.p10[i] <= result.p25[i]
            assert result.p25[i] <= result.median[i]
            assert result.median[i] <= result.p75[i]
            assert result.p75[i] <= result.p90[i]

    def test_deterministic_with_seed(self):
        r1 = monte_carlo(10000, 100, seed=123, n_simulations=100, years=5)
        r2 = monte_carlo(10000, 100, seed=123, n_simulations=100, years=5)
        assert r1.median == r2.median

    def test_zero_volatility(self):
        result = monte_carlo(
            10000, 0, annual_return=0.07, annual_volatility=0.0001,
            years=5, n_simulations=100, seed=42,
        )
        # All paths should be very similar
        for i in range(5):
            spread = result.p90[i] - result.p10[i]
            assert spread < result.median[i] * 0.2  # within 20%
