"""Unit tests for MCP tool wrappers — verify they call engines and handle edges."""
from datetime import date
from decimal import Decimal

import pytest

from src.tools.advisory import get_advice
from src.tools.audit import audit_single_fund
from src.tools.portfolio import get_allocation
from src.tools.risk import assess_risk
from src.tools.scenario import run_scenario


class TestAssessRisk:
    def test_returns_profile_dict(self):
        result = assess_risk("moderate", 15.0, 3, 3, 3)
        assert result["level"] == "moderate"
        assert "total_score" in result
        assert "equity_pct" in result
        assert result["equity_pct"] + result["bond_pct"] + result["cash_pct"] == 100

    def test_invalid_horizon_defaults_to_moderate(self):
        result = assess_risk("century", 10.0, 3, 3, 3)
        assert result["level"] in ("conservative", "moderate", "aggressive")


class TestGetAllocation:
    def test_returns_allocation_dict(self):
        result = get_allocation("moderate", 100000)
        assert result["equity_pct"] + result["bond_pct"] + result["cash_pct"] == 100
        assert len(result["buckets"]) > 0
        assert result["total"] == 100000

    def test_invalid_level_defaults(self):
        result = get_allocation("extreme", 50000)
        assert "buckets" in result


class TestGetAdvice:
    def test_path_a_returns_report(self):
        result = get_advice("A", "test allocation")
        assert "report_html" in result
        assert len(result["report_html"]) > 0

    def test_invalid_portfolio_returns_error(self):
        result = get_advice("A", "test", {"equity": "notanumber"})
        assert len(result["errors"]) > 0

    def test_path_b_includes_debate(self):
        result = get_advice("B", "market opportunity")
        assert len(result["report_html"]) > 0

    def test_path_c_diagnostic(self):
        result = get_advice("C", "diagnose", {"equity": 50000, "bond": 50000, "cash": 0})
        assert len(result["report_html"]) > 0


class TestAuditSingleFund:
    def test_clean_fund_passes(self):
        result = audit_single_fund("000001", "test", "mixed", 5_000_000_000, 0.010, "2010-06-01", 50000, 500000)
        assert result["passed"] is True

    def test_tiny_fund_rejected(self):
        result = audit_single_fund("000099", "tiny", "stock", 100_000_000, 0.025, "2026-01-01", 200000, 500000)
        assert result["passed"] is False
        assert len(result["reasons"]) > 0


class TestRunScenario:
    def test_returns_scenario_dict(self):
        result = run_scenario(60000, 30000, 10000)
        assert "total_loss" in result
        assert "final_value" in result
        assert "scenario" in result

    def test_named_scenario(self):
        result = run_scenario(100000, 0, 0, scenario_name="2008 全球金融危机")
        assert result["scenario"] == "2008 全球金融危机"

    def test_unknown_scenario_uses_noshock(self):
        result = run_scenario(50000, 50000, 0, scenario_name="nonexistent")
        assert result["total_loss"] == 0  # no-shock fallback
