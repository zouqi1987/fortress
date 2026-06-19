"""Tests for src/engine/risk_profile.py — 5-factor risk assessment."""
from decimal import Decimal

import pytest

from src.engine.risk_profile import (
    InvestmentHorizon,
    RiskLevel,
    RiskProfile,
    RiskScore,
    assess_risk_profile,
)


class TestRiskProfile:
    def test_all_min_scores_yields_conservative(self):
        profile = assess_risk_profile(
            horizon=InvestmentHorizon.SHORT,
            max_loss_pct=Decimal("5"),
            income_stability=1,
            experience=1,
            liquidity_need=1,
        )
        assert profile.level == RiskLevel.CONSERVATIVE
        assert profile.total_score < 30

    def test_all_max_scores_yields_aggressive(self):
        profile = assess_risk_profile(
            horizon=InvestmentHorizon.LONG,
            max_loss_pct=Decimal("30"),
            income_stability=5,
            experience=5,
            liquidity_need=5,
        )
        assert profile.level == RiskLevel.AGGRESSIVE
        assert profile.total_score >= 70

    def test_mid_scores_yields_moderate(self):
        profile = assess_risk_profile(
            horizon=InvestmentHorizon.MEDIUM,
            max_loss_pct=Decimal("15"),
            income_stability=3,
            experience=3,
            liquidity_need=3,
        )
        assert profile.level == RiskLevel.MODERATE

    def test_output_contains_all_scores(self):
        profile = assess_risk_profile(
            horizon=InvestmentHorizon.MEDIUM,
            max_loss_pct=Decimal("10"),
            income_stability=4,
            experience=2,
            liquidity_need=3,
        )
        assert isinstance(profile.scores, RiskScore)
        assert 0 <= profile.scores.horizon <= 20
        assert 0 <= profile.scores.loss_tolerance <= 20
        assert 0 <= profile.scores.income_stability <= 20
        assert 0 <= profile.scores.experience <= 20
        assert 0 <= profile.scores.liquidity <= 20

    def test_default_recommendation_includes_allocation_hint(self):
        profile = assess_risk_profile(
            horizon=InvestmentHorizon.LONG,
            max_loss_pct=Decimal("20"),
            income_stability=4,
            experience=3,
            liquidity_need=4,
        )
        assert profile.equity_pct > 0
        assert profile.bond_pct > 0
        assert profile.cash_pct > 0
        assert profile.equity_pct + profile.bond_pct + profile.cash_pct == 100

    @pytest.mark.parametrize(
        "horizon,loss,income,exp,liq,expected",
        [
            (InvestmentHorizon.SHORT, Decimal("5"), 1, 1, 1, RiskLevel.CONSERVATIVE),
            (InvestmentHorizon.LONG, Decimal("30"), 5, 5, 5, RiskLevel.AGGRESSIVE),
            (InvestmentHorizon.LONG, Decimal("10"), 3, 4, 3, RiskLevel.MODERATE),
            (InvestmentHorizon.SHORT, Decimal("25"), 2, 5, 1, RiskLevel.MODERATE),
            (InvestmentHorizon.SHORT, Decimal("5"), 1, 1, 5, RiskLevel.CONSERVATIVE),
        ],
    )
    def test_edge_cases(self, horizon, loss, income, exp, liq, expected):
        profile = assess_risk_profile(horizon, loss, income, exp, liq)
        assert profile.level == expected
