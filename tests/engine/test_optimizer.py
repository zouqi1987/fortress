"""Tests for src/engine/optimizer.py — min-variance portfolio optimization."""
from decimal import Decimal

import pytest

from src.engine.optimizer import (
    OptimizerConfig,
    OptimizationResult,
    optimize_portfolio,
)


class TestOptimizer:
    def test_empty_returns_returns_empty(self):
        config = OptimizerConfig()
        result = optimize_portfolio({}, config)
        assert result.weights == {}
        assert result.success is True

    def test_single_asset_honors_max_weight(self):
        returns = {"000001": [0.01, 0.02, -0.01, 0.005, 0.015]}
        config = OptimizerConfig()
        result = optimize_portfolio(returns, config)
        assert result.success
        assert len(result.weights) == 1
        assert float(list(result.weights.values())[0]) == pytest.approx(0.30, abs=0.01)

    def test_config_defaults(self):
        config = OptimizerConfig()
        assert config.max_weight == Decimal("0.30")
        assert config.min_weight == Decimal("0.01")

    def test_result_weights_sum_to_one(self):
        returns = {
            "000001": [0.01, 0.02, -0.01],
            "000002": [0.005, 0.01, 0.02],
            "000003": [-0.01, 0.00, 0.01],
        }
        config = OptimizerConfig()
        result = optimize_portfolio(returns, config)
        if result.weights:
            total = sum((float(w) for w in result.weights.values()), 0.0)
            assert total == pytest.approx(1.0, abs=0.02)

    def test_min_variance_produces_differentiated_weights(self):
        """Min-variance should allocate more to lower-vol assets."""
        returns = {
            "low_vol": [0.001] * 100,
            "high_vol": [0.01 if i % 2 == 0 else -0.009 for i in range(100)],
        }
        config = OptimizerConfig(max_weight=Decimal("0.80"))
        result = optimize_portfolio(returns, config)
        assert result.success
        w_low = float(result.weights["low_vol"])
        w_high = float(result.weights["high_vol"])
        # Low-vol asset should get more weight in min-variance
        assert w_low > w_high, f"low_vol={w_low:.2%} should > high_vol={w_high:.2%}"

    def test_insufficient_data_falls_back(self):
        """Fewer than 2 observations → equal weight fallback."""
        returns = {"A": [0.01], "B": [0.02]}
        result = optimize_portfolio(returns, OptimizerConfig())
        # Single observation → insufficient for covariance
        assert not result.success

    def test_constraints_respected(self):
        """All weights within [min_weight, max_weight] and sum to 1."""
        import random
        random.seed(123)
        returns = {
            f"fund_{i}": [random.gauss(0.0005, 0.015) for _ in range(252)]
            for i in range(5)
        }
        config = OptimizerConfig(max_weight=Decimal("0.40"), min_weight=Decimal("0.05"))
        result = optimize_portfolio(returns, config)
        assert result.success
        for code, w in result.weights.items():
            assert float(w) >= 0.04, f"{code}={float(w):.3f} below min"
            assert float(w) <= 0.41, f"{code}={float(w):.3f} above max"
        total = sum(float(w) for w in result.weights.values())
        assert total == pytest.approx(1.0, abs=0.01)
