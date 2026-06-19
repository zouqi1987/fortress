"""MCP tool: scenario stress testing."""
from decimal import Decimal

from src.engine.stress_tester import HISTORICAL_SCENARIOS, Scenario, run_stress_test


def run_scenario(equity: float, bond: float, cash: float, scenario_name: str | None = None) -> dict:
    """Run a stress test scenario against a portfolio.

    Args:
        equity: equity amount in CNY
        bond: bond amount in CNY
        cash: cash amount in CNY
        scenario_name: name of historical scenario (or None for worst-case)
    """
    portfolio = {
        "equity": Decimal(str(equity)),
        "bond": Decimal(str(bond)),
        "cash": Decimal(str(cash)),
    }

    if scenario_name:
        scenario = next((s for s in HISTORICAL_SCENARIOS if s.name == scenario_name), None)
        if scenario is None:
            scenario = Scenario(name=scenario_name)  # no-shock fallback
    else:
        # Use worst historical scenario
        scenario = max(HISTORICAL_SCENARIOS, key=lambda s: abs(s.equity_shock or Decimal("0")))

    result = run_stress_test(portfolio, scenario)

    return {
        "scenario": result.scenario_name,
        "total_loss": float(result.total_loss),
        "loss_pct": float(result.loss_pct),
        "final_value": float(result.final_value),
        "equity_impact": float(result.equity_impact),
        "bond_impact": float(result.bond_impact),
        "cash_impact": float(result.cash_impact),
    }
