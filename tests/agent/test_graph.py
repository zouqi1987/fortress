"""Integration tests for the LangGraph agent DAG."""
from decimal import Decimal

import pytest

from src.agent.graph import build_graph
from src.agent.state import create_initial_state
from src.engine.risk_profile import (
    InvestmentHorizon,
    RiskLevel,
    RiskProfile,
    RiskScore,
)


def _mock_risk_profile():
    return RiskProfile(
        level=RiskLevel.MODERATE,
        scores=RiskScore(horizon=10, loss_tolerance=12, income_stability=15, experience=10, liquidity=10),
        total_score=57, equity_pct=60, bond_pct=30, cash_pct=10,
    )


class TestGraphRouting:
    def test_path_a_runs_full_pipeline(self):
        graph = build_graph()
        state = create_initial_state("A", "allocate my portfolio")
        state["portfolio"] = {"equity": Decimal("60000"), "bond": Decimal("30000"), "cash": Decimal("10000")}
        state["risk_profile"] = _mock_risk_profile()

        result = graph.invoke(state)
        assert result.get("report_html") is not None
        assert len(result.get("report_html", "")) > 0

    def test_path_b_includes_debate(self):
        graph = build_graph()
        state = create_initial_state("B", "market opportunity in tech")
        state["market_data"] = {"000001": []}
        state["portfolio"] = {"equity": Decimal("50000"), "bond": Decimal("50000"), "cash": Decimal("0")}
        state["risk_profile"] = _mock_risk_profile()

        result = graph.invoke(state)
        assert result.get("debate_result") is not None
        assert "多方信号" in result.get("debate_result", "")

    def test_path_c_runs_diagnostic(self):
        graph = build_graph()
        state = create_initial_state("C", "diagnose my holdings")
        state["portfolio"] = {"equity": Decimal("70000"), "bond": Decimal("20000"), "cash": Decimal("10000")}
        state["holdings"] = [
            {"code": "000001", "amount": Decimal("50000")},
            {"code": "000002", "amount": Decimal("20000")},
        ]

        result = graph.invoke(state)
        assert result.get("health_check") is not None
        assert result.get("stress_result") is not None

    def test_compiles_without_error(self):
        graph = build_graph()
        assert graph is not None
        # Verify all 5 nodes registered
        nodes = list(graph.get_graph().nodes.keys())
        assert "data_collector" in nodes
        assert "reporter" in nodes

    def test_empty_state_survives(self):
        """Graph should not crash on minimal state."""
        graph = build_graph()
        state = create_initial_state("A", "hello")
        result = graph.invoke(state)
        assert "report_html" in result
        # Even with missing data, the reporter emits a basic report
        assert len(result["report_html"]) > 0
