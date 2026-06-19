"""Tests for src/engine/health_checker.py — portfolio health scoring."""
from decimal import Decimal

from src.engine.health_checker import (
    HealthCheckResult,
    check_portfolio_health,
)
from src.engine.risk_profile import RiskLevel


class TestHealthChecker:
    def test_balanced_portfolio_scores_high(self):
        result = check_portfolio_health(
            equity_pct=50,
            bond_pct=40,
            cash_pct=10,
            risk_level=RiskLevel.MODERATE,
            fee_ratio=Decimal("0.010"),
            max_drawdown_pct=Decimal("10"),
            num_holdings=5,
        )
        assert result.overall_score >= 60
        assert result.grade in ("A", "B")

    def test_concentrated_portfolio_scores_low(self):
        result = check_portfolio_health(
            equity_pct=90,
            bond_pct=5,
            cash_pct=5,
            risk_level=RiskLevel.CONSERVATIVE,
            fee_ratio=Decimal("0.020"),
            max_drawdown_pct=Decimal("30"),
            num_holdings=2,
        )
        assert result.overall_score < 60
        assert result.grade in ("C", "D")

    def test_result_includes_all_dimensions(self):
        result = check_portfolio_health(
            equity_pct=60,
            bond_pct=30,
            cash_pct=10,
            risk_level=RiskLevel.MODERATE,
            fee_ratio=Decimal("0.012"),
            max_drawdown_pct=Decimal("15"),
            num_holdings=4,
        )
        assert result.drift_score > 0
        assert result.diversification_score > 0
        assert result.fee_score > 0
        assert result.drawdown_score > 0
        assert 0 <= result.overall_score <= 100

    def test_aggressive_with_high_equity_is_healthy(self):
        result = check_portfolio_health(
            equity_pct=80,
            bond_pct=15,
            cash_pct=5,
            risk_level=RiskLevel.AGGRESSIVE,
            fee_ratio=Decimal("0.008"),
            max_drawdown_pct=Decimal("20"),
            num_holdings=6,
        )
        assert result.overall_score >= 60

    def test_too_many_holdings_penalizes(self):
        """超过配置建议的持仓数量会扣分"""
        result_many = check_portfolio_health(
            equity_pct=60, bond_pct=30, cash_pct=10,
            risk_level=RiskLevel.MODERATE,
            fee_ratio=Decimal("0.010"),
            max_drawdown_pct=Decimal("10"),
            num_holdings=15,
        )
        result_few = check_portfolio_health(
            equity_pct=60, bond_pct=30, cash_pct=10,
            risk_level=RiskLevel.MODERATE,
            fee_ratio=Decimal("0.010"),
            max_drawdown_pct=Decimal("10"),
            num_holdings=5,
        )
        assert result_many.diversification_score < result_few.diversification_score

    def test_single_holding(self):
        result = check_portfolio_health(
            equity_pct=60, bond_pct=30, cash_pct=10,
            risk_level=RiskLevel.MODERATE,
            fee_ratio=Decimal("0.010"),
            max_drawdown_pct=Decimal("10"),
            num_holdings=1,
        )
        assert result.diversification_score < 25  # penalty for too few

    def test_zero_holdings(self):
        result = check_portfolio_health(
            equity_pct=60, bond_pct=30, cash_pct=10,
            risk_level=RiskLevel.MODERATE,
            fee_ratio=Decimal("0.010"),
            max_drawdown_pct=Decimal("10"),
            num_holdings=0,
        )
        assert result.diversification_score < 20
