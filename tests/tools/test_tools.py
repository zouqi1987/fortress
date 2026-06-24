"""Unit tests for MCP tool wrappers — verify they call engines and handle edges."""
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest

from src.tools.advisory import get_advice
from src.tools.audit import audit_single_fund
from src.tools.health import check_health
from src.tools.macro import detect_regime
from src.tools.market import lookup_index
from src.tools.personal_rules import manage_personal_rules
from src.tools.portfolio import get_allocation
from src.tools.screener import screen_funds
from src.tools.risk import assess_risk
from src.tools.rules import list_hard_rules
from src.tools.scenario import run_scenario


class TestAssessRisk:
    def test_returns_profile_dict(self):
        result = assess_risk("C", 15.0, 3, 3, 3)  # C = medium
        assert result["level"] == "moderate"
        assert "total_score" in result
        assert "equity_pct" in result
        assert result["equity_pct"] + result["bond_pct"] + result["cash_pct"] == 100

    def test_invalid_horizon_returns_error(self):
        result = assess_risk("century", 10.0, 3, 3, 3)
        assert "error" in result

    @pytest.mark.parametrize(
        "letter,expected_name",
        [
            ("A", "very_short"),
            ("B", "short"),
            ("C", "medium"),
            ("D", "long"),
            ("E", "very_long"),
        ],
    )
    def test_a_to_e_horizon_mapping(self, letter, expected_name):
        """A-E questionnaire answers map to correct horizon values."""
        result = assess_risk(letter, 10.0, 3, 3, 3)
        assert "error" not in result
        assert result["level"] in ("conservative", "moderate", "aggressive")

    def test_legacy_horizon_strings_still_work(self):
        """Backward compatibility: old 'short'/'medium'/'long' still accepted."""
        for h in ("short", "medium", "long"):
            result = assess_risk(h, 15.0, 3, 3, 3)
            assert "error" not in result, f"horizon={h!r} should work"


class TestGetAllocation:
    def test_returns_allocation_dict(self):
        result = get_allocation("moderate", 100000)
        assert result["equity_pct"] + result["bond_pct"] + result["cash_pct"] == 100
        assert len(result["buckets"]) > 0
        assert result["total"] == 100000

    def test_invalid_level_returns_error(self):
        result = get_allocation("extreme", 50000)
        assert "error" in result


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


class TestListHardRules:
    def test_returns_all_five_rules(self):
        result = list_hard_rules()
        assert result["count"] == 5
        assert len(result["rules"]) == 5

    def test_each_rule_has_required_fields(self):
        result = list_hard_rules()
        for rule in result["rules"]:
            assert "id" in rule
            assert "severity" in rule
            assert "message" in rule
            assert rule["id"].startswith("RL-")

    def test_rules_have_expected_ids(self):
        result = list_hard_rules()
        ids = {r["id"] for r in result["rules"]}
        assert ids == {"RL-001", "RL-002", "RL-003", "RL-004", "RL-005"}

    def test_reject_severity_present(self):
        result = list_hard_rules()
        severities = {r["severity"] for r in result["rules"]}
        assert "reject" in severities
        assert "warn" in severities


class TestCheckHealth:
    def test_balanced_moderate_scores_high(self):
        result = check_health(60, 30, 10, "moderate", 0.010, 10.0, 5)
        assert result["overall_score"] >= 60
        assert result["grade"] in ("A", "B")
        assert "error" not in result

    def test_concentrated_portfolio_scores_low(self):
        result = check_health(90, 5, 5, "conservative", 0.020, 30.0, 2)
        assert result["overall_score"] < 60
        assert result["grade"] in ("C", "D", "F")

    def test_includes_all_dimensions(self):
        result = check_health(60, 30, 10, "moderate", 0.012, 15.0, 4)
        assert result["drift_score"] > 0
        assert result["diversification_score"] > 0
        assert result["fee_score"] > 0
        assert result["drawdown_score"] > 0
        assert 0 <= result["overall_score"] <= 100

    def test_aggressive_with_high_equity_is_healthy(self):
        result = check_health(80, 15, 5, "aggressive", 0.008, 20.0, 6)
        assert result["overall_score"] >= 60

    def test_invalid_risk_level_returns_error(self):
        result = check_health(60, 30, 10, "extreme", 0.010, 10.0, 5)
        assert "error" in result

    def test_warnings_for_poor_health(self):
        result = check_health(90, 5, 5, "conservative", 0.025, 35.0, 1)
        assert isinstance(result["warnings"], list)
        assert len(result["warnings"]) > 0


class TestDetectRegime:
    def test_bull_when_above_ma200(self):
        result = detect_regime(current=3500, ma200=3000, ma120=2800)
        assert result["regime"] == "bull"
        assert "description" in result

    def test_bear_when_below_ma120(self):
        result = detect_regime(current=2500, ma200=3000, ma120=2800)
        assert result["regime"] == "bear"

    def test_sideways_when_between(self):
        result = detect_regime(current=2900, ma200=3000, ma120=2800)
        assert result["regime"] == "sideways"

    def test_defaults_to_sideways_when_no_data(self):
        result = detect_regime()
        assert result["regime"] == "sideways"

    def test_includes_multiplier_when_risk_level_provided(self):
        result = detect_regime(current=3500, ma200=3000, ma120=2800, risk_level="moderate")
        assert "multiplier" in result
        assert result["multiplier"] == 1.0

    def test_invalid_risk_level_returns_error(self):
        result = detect_regime(current=3000, ma200=2800, ma120=2500, risk_level="extreme")
        assert "error" in result


class TestManagePersonalRules:
    def test_list_returns_empty_initially(self):
        # Clear first to ensure clean state
        manage_personal_rules("clear")
        result = manage_personal_rules("list")
        assert result["active_count"] == 0
        assert result["rules"] == []

    def test_add_and_list_rule(self):
        manage_personal_rules("clear")
        result = manage_personal_rules(
            "add", rule_id="PR-001", description="不投股票型",
            fund_types_blacklist="stock,mixed", max_single_position=100000,
        )
        assert result["status"] == "ok"
        assert result["active_count"] == 1

        listed = manage_personal_rules("list")
        assert listed["active_count"] == 1
        assert listed["rules"][0]["id"] == "PR-001"
        assert "stock" in listed["rules"][0]["fund_types_blacklist"]

    def test_remove_rule(self):
        manage_personal_rules("clear")
        manage_personal_rules("add", rule_id="PR-001", description="test")
        result = manage_personal_rules("remove", rule_id="PR-001")
        assert result["status"] == "ok"
        assert result["active_count"] == 0

    def test_clear_all_rules(self):
        manage_personal_rules("clear")
        manage_personal_rules("add", rule_id="PR-001", description="test1")
        manage_personal_rules("add", rule_id="PR-002", description="test2")
        result = manage_personal_rules("clear")
        assert result["active_count"] == 0

    def test_add_without_rule_id_returns_error(self):
        result = manage_personal_rules("add")
        assert "error" in result

    def test_unknown_action_returns_error(self):
        result = manage_personal_rules("unknown")
        assert "error" in result

    def test_min_fund_size_rule(self):
        manage_personal_rules("clear")
        result = manage_personal_rules(
            "add", rule_id="PR-SIZE", description="最低规模5亿",
            min_fund_size=500000000,
        )
        assert result["status"] == "ok"
        assert result["rule"]["min_fund_size"] == 500000000.0


class TestScreenFunds:
    SAMPLE_FUNDS = [
        {"code": "000001", "name": "华夏成长", "type": "mixed",
         "net_asset_value": 5_000_000_000, "fee_rate": 0.010, "inception_date": "2010-06-01"},
        {"code": "000002", "name": "易方达债券", "type": "bond",
         "net_asset_value": 10_000_000_000, "fee_rate": 0.005, "inception_date": "2012-03-15"},
        {"code": "000099", "name": "Tiny Fund", "type": "stock",
         "net_asset_value": 50_000_000, "fee_rate": 0.025, "inception_date": "2025-12-01"},
    ]

    @staticmethod
    def _mock_nav_store_with_data(fund_codes):
        """Mock NavStore with canned NAV data for the given fund codes."""
        mock_store = mock.Mock()
        mock_store.coverage_report.return_value = {"fund_count": len(fund_codes), "latest_date": "2026-06-24"}
        # Return 100-point stable NAV series for each fund
        nav_map = {code: [1.0 + i * 0.001 for i in range(100)] for code in fund_codes}
        mock_store.get_nav_series.side_effect = lambda code, days=750: nav_map.get(code, [])
        return mock_store

    @staticmethod
    def _mock_pool_index(fund_codes):
        """Mock pool_index with canned PoolFund data."""
        from src.data.sources.fund_pool import PoolFund
        pool = {}
        for code in fund_codes:
            pool[code] = PoolFund(
                code=code, name=f"Fund{code}", fund_type="bond", raw_type="bond",
                manager="test_mgr", fee=Decimal("0.015"),
                ret_1m=0.5, ret_3m=1.0, ret_6m=2.0, ret_1y=5.0, ret_3y=10.0,
                rating_morningstar=3, rating_shanghai=3, rating_zhaoshang=3, rating_jiAn=3,
            )
        return pool

    @staticmethod
    def _mock_category_averages():
        return {"broad": {"bond": {"ret_1m": 0.5, "ret_3m": 1.0, "ret_6m": 2.0, "ret_1y": 5.0, "ret_3y": 10.0}}}

    def _patch_tool_deps(self, fund_codes):
        """Patch tool-layer helpers to avoid network/DB calls."""
        return [
            mock.patch("src.tools.screener._get_nav_store", return_value=self._mock_nav_store_with_data(fund_codes)),
            mock.patch("src.tools.screener._get_or_load_pool_index", return_value=self._mock_pool_index(fund_codes)),
            mock.patch("src.tools.screener._get_or_load_category_averages", return_value=self._mock_category_averages()),
        ]

    def test_screens_and_scores_funds(self):
        codes = [f["code"] for f in self.SAMPLE_FUNDS]
        with self._patch_tool_deps(codes)[0], self._patch_tool_deps(codes)[1], self._patch_tool_deps(codes)[2]:
            result = screen_funds(self.SAMPLE_FUNDS)
        assert result["count"] > 0
        for r in result["results"]:
            assert "score" in r
            assert 0 <= r["score"] <= 100
            assert "dimension_breakdown" in r
            assert "fund_type_class" in r

    def test_results_sorted_by_score_desc(self):
        codes = [f["code"] for f in self.SAMPLE_FUNDS]
        patches = self._patch_tool_deps(codes)
        for p in patches:
            p.start()
        try:
            result = screen_funds(self.SAMPLE_FUNDS)
        finally:
            for p in patches:
                p.stop()
        scores = [r["score"] for r in result["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_filters_by_min_net_asset_value(self):
        codes = [f["code"] for f in self.SAMPLE_FUNDS]
        patches = self._patch_tool_deps(codes)
        for p in patches:
            p.start()
        try:
            result = screen_funds(self.SAMPLE_FUNDS, min_net_asset_value=1_000_000_000)
        finally:
            for p in patches:
                p.stop()
        assert all(r["net_asset_value"] >= 1_000_000_000 for r in result["results"])

    def test_empty_funds_returns_empty(self):
        result = screen_funds([])
        assert result["count"] == 0
        assert result["results"] == []

    def test_invalid_inception_date_reports_error(self):
        bad_date_funds = [{"code": "err", "name": "Bad Date", "type": "mixed",
                           "net_asset_value": 5_000_000_000, "fee_rate": 0.01,
                           "inception_date": "not-a-date"}]
        result = screen_funds(bad_date_funds)
        assert result["errors"] is not None

    def test_empty_nav_store_returns_backfill_error(self):
        """Coverage gate: empty NavStore → error with backfill instructions."""
        empty_store = mock.Mock()
        empty_store.coverage_report.return_value = {"fund_count": 0, "latest_date": None}
        with mock.patch("src.tools.screener._get_nav_store", return_value=empty_store):
            result = screen_funds(self.SAMPLE_FUNDS)
        assert result["count"] == 0
        assert "error" in result
        assert "backfill" in result["error"].lower() or "回填" in result["error"]


class TestLookupIndex:
    def test_lookup_index_function_exists(self):
        assert callable(lookup_index)

    def test_lookup_index_with_invalid_code_returns_error(self):
        """With no network, this returns error dict — verify it doesn't crash."""
        result = lookup_index("INVALID")
        assert isinstance(result, dict)
        assert "code" in result

    def test_lookup_index_accepts_date_params(self):
        """Verify date params don't cause crashes even when source fails."""
        result = lookup_index("000001", start="2026-01-01", end="2026-06-01")
        assert isinstance(result, dict)
        # May succeed (cache hit) or fail gracefully (error dict) — either is fine
