"""Tests for agent DAG nodes — pure functions: (state) → state_update."""
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest

from src.agent.nodes.data_collector import data_collector_node
from src.agent.nodes.debater import debater_node
from src.agent.nodes.allocator import allocator_node
from src.agent.nodes.risk_assessor import risk_assessor_node
from src.agent.nodes.reporter import reporter_node
from src.agent.state import create_initial_state
from src.datatypes import FundInfo
from src.engine.allocation import AllocationLayer, AllocationPlan, Bucket
from src.engine.auditor import AuditResult
from src.engine.health_checker import HealthCheckResult
from src.engine.risk_profile import InvestmentHorizon, RiskLevel, RiskProfile, RiskScore
from src.engine.stress_tester import StressResult


# ── Mock factories ───────────────────────────────────────────────────


def mock_risk_profile():
    return RiskProfile(
        level=RiskLevel.MODERATE,
        scores=RiskScore(horizon=10, loss_tolerance=12, income_stability=15, experience=10, liquidity=10),
        total_score=57, equity_pct=60, bond_pct=30, cash_pct=10,
    )


def mock_allocation_plan():
    return AllocationPlan(
        layers=(
            AllocationLayer("活钱", 0, 20, 80),
            AllocationLayer("稳健", 30, 60, 10),
            AllocationLayer("增值", 70, 25, 5),
        ),
        layer_weights=(Decimal("0.2"), Decimal("0.45"), Decimal("0.35")),
        buckets=(Bucket("活钱-货币", Decimal("20000"), "money", "活钱"),),
        total=Decimal("100000"),
    )


# ── Tests ───────────────────────────────────────────────────────────


class TestDataCollectorNode:
    def test_populates_portfolio_and_market_data(self):
        state = create_initial_state("A", "analyze my portfolio")
        result = data_collector_node(state)
        assert "portfolio" in result

    def test_errors_on_failure_gracefully(self):
        state = create_initial_state("A", "test")
        # With no external deps configured, should not crash
        result = data_collector_node(state)
        assert "errors" in result or "portfolio" in result


class TestDebaterNode:
    def test_returns_structured_signals(self):
        state = create_initial_state("B", "market opportunity")
        state["market_data"] = {"000001": [{"date": "2026-06-19", "nav": 1.5}]}
        state["holdings"] = [
            {"code": "000001", "name": "华夏成长"},
            {"code": "000002", "name": "债券稳健"},
        ]
        result = debater_node(state)
        assert "debate_result" in result
        debate = result.get("debate_result", "")
        assert isinstance(debate, str) and len(debate) > 0
        # Should contain signal markers, not LLM fallback text
        assert "多方信号" in debate or "空方信号" in debate

    def test_no_market_data_graceful(self):
        state = create_initial_state("B", "opportunity")
        result = debater_node(state)
        assert "errors" in result


class TestAllocatorNode:
    def test_returns_allocation_plan(self):
        state = create_initial_state("A", "allocate")
        state["risk_profile"] = mock_risk_profile()
        result = allocator_node(state)
        assert "allocation_plan" in result

    def test_no_risk_profile_errors(self):
        state = create_initial_state("A", "allocate")
        result = allocator_node(state)
        assert "errors" in result


class TestRiskAssessorNode:
    def test_returns_risk_assessment(self):
        state = create_initial_state("C", "diagnose")
        state["portfolio"] = {"equity": Decimal("60000"), "bond": Decimal("30000"), "cash": Decimal("10000")}
        result = risk_assessor_node(state)
        assert "health_check" in result
        assert "stress_result" in result

    def test_no_portfolio_errors(self):
        state = create_initial_state("C", "diagnose")
        result = risk_assessor_node(state)
        assert "errors" in result


class TestReporterNode:
    def test_returns_html_report(self):
        state = create_initial_state("A", "report")
        state["risk_profile"] = mock_risk_profile()
        state["allocation_plan"] = mock_allocation_plan()
        state["audit_results"] = [AuditResult("000001", True, "pass", ())]
        state["stress_result"] = StressResult("test", Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("100000"), Decimal("0"))
        state["health_check"] = HealthCheckResult(80, "A", 30, 25, 15, 10, ())

        result = reporter_node(state)
        report = result.get("report_html", "")
        assert isinstance(report, str) and len(report) > 0
        assert "<html>" in report.lower() or "<div" in report.lower() or "<table" in report.lower()

    def test_minimal_state_produces_report(self):
        state = create_initial_state("A", "minimal report")
        result = reporter_node(state)
        report = result.get("report_html", "")
        assert len(report) > 0
