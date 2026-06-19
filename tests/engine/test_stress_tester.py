"""Tests for src/engine/stress_tester.py — scenario stress testing."""
from decimal import Decimal

import pytest

from src.engine.stress_tester import (
    HISTORICAL_SCENARIOS,
    Scenario,
    StressResult,
    run_stress_test,
)


@pytest.fixture
def sample_portfolio() -> dict[str, Decimal]:
    return {
        "equity": Decimal("60000"),
        "bond": Decimal("30000"),
        "cash": Decimal("10000"),
    }


class TestStressTester:
    def test_equity_crash_impacts_equity_heavily(self, sample_portfolio):
        scenario = Scenario(
            name="equity crash",
            equity_shock=Decimal("-0.40"),
        )
        result = run_stress_test(sample_portfolio, scenario)
        assert result.total_loss < Decimal("0")
        # 40% equity crash on 60k equity = 24k loss on 100k total = -24%
        expected_loss = Decimal("60000") * Decimal("0.40")
        assert abs(result.total_loss + expected_loss) < Decimal("100")

    def test_no_shock_preserves_portfolio(self, sample_portfolio):
        scenario = Scenario(name="no change")
        result = run_stress_test(sample_portfolio, scenario)
        assert result.total_loss == Decimal("0")
        assert result.final_value == sum(sample_portfolio.values())

    def test_bond_only_shock(self):
        portfolio = {"equity": Decimal("0"), "bond": Decimal("100000"), "cash": Decimal("0")}
        scenario = Scenario(name="rate hike", bond_shock=Decimal("-0.10"))
        result = run_stress_test(portfolio, scenario)
        assert result.total_loss == Decimal("-10000")

    def test_historical_scenarios_exist(self):
        assert len(HISTORICAL_SCENARIOS) >= 4
        for s in HISTORICAL_SCENARIOS:
            assert isinstance(s.name, str)
            assert len(s.name) > 0

    def test_result_includes_all_asset_impacts(self, sample_portfolio):
        scenario = Scenario(
            name="mixed",
            equity_shock=Decimal("-0.20"),
            bond_shock=Decimal("0.05"),
        )
        result = run_stress_test(sample_portfolio, scenario)
        assert result.equity_impact < Decimal("0")  # negative shock
        assert result.bond_impact > Decimal("0")  # positive shock
        assert result.cash_impact == Decimal("0")  # cash unaffected

    def test_custom_positive_scenario(self, sample_portfolio):
        scenario = Scenario(
            name="bull market",
            equity_shock=Decimal("0.30"),
            bond_shock=Decimal("0.05"),
        )
        result = run_stress_test(sample_portfolio, scenario)
        assert result.total_loss > Decimal("0")  # gain
