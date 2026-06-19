"""Tests for src/engine/optimizer.py — Riskfolio-Lib portfolio optimization."""
from decimal import Decimal

import pytest

from src.engine.optimizer import (
    OptimizerConfig,
    OptimizationResult,
    optimize_portfolio,
)


class TestOptimizer:
    def test_empty_returns_returns_equal_weight(self):
        """With no historical returns, fall back to equal weight."""
        config = OptimizerConfig(risk_measure="MV")
        result = optimize_portfolio({}, config)
        assert result.weights == {}
        assert result.success is True

    def test_single_asset_honors_max_weight(self):
        """Single asset → capped at max_weight (default 0.30)."""
        returns = {"000001": [0.01, 0.02, -0.01, 0.005, 0.015]}
        config = OptimizerConfig(risk_measure="MV")
        result = optimize_portfolio(returns, config)
        assert result.success
        assert len(result.weights) == 1
        assert float(list(result.weights.values())[0]) == pytest.approx(0.30, abs=0.01)

    def test_config_defaults(self):
        config = OptimizerConfig()
        assert config.risk_measure == "MV"
        assert config.max_weight == Decimal("0.30")
        assert config.min_weight == Decimal("0.01")

    def test_result_weights_sum_to_one(self):
        returns = {
            "000001": [0.01, 0.02, -0.01],
            "000002": [0.005, 0.01, 0.02],
            "000003": [-0.01, 0.00, 0.01],
        }
        config = OptimizerConfig(risk_measure="MV")
        result = optimize_portfolio(returns, config)
        if result.weights:
            total = sum((float(w) for w in result.weights.values()), 0.0)
            assert total == pytest.approx(1.0, abs=0.02)

    @pytest.mark.integration
    @pytest.mark.xfail(reason="riskfolio-lib v7.3 numpy/scipy compat issue — known, harmless")
    def test_riskfolio_lib_integration(self):
        """Smoke test that riskfolio-lib is importable and functional."""
        import pandas as pd
        import riskfolio as rp

        returns = pd.DataFrame({
            "A": [0.01, 0.02, -0.01],
            "B": [0.005, 0.01, 0.02],
            "C": [-0.01, 0.00, 0.01],
        })
        port = rp.Portfolio(returns=returns)
        w = port.optimization(model="Classic", rm="MV", obj="MinRisk", rf=0.02)
        assert w is not None
        assert len(w) == 3
