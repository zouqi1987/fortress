"""Risk assessor node — runs stress test and health check.

Pure function: (state) → state_update dict.
Active on paths A, B, and C.
"""
from decimal import Decimal

from src.agent.state import ConversationState
from src.engine.health_checker import check_portfolio_health
from src.engine.risk_profile import RiskLevel
from src.engine.stress_tester import HISTORICAL_SCENARIOS, run_stress_test


def risk_assessor_node(state: ConversationState) -> dict:
    """Run stress test and health check on current portfolio.

    Requires portfolio in state. Returns stress_result and health_check.
    """
    portfolio = state.get("portfolio")

    if not portfolio:
        return {
            "errors": state.get("errors", []) + ["risk_assessor: no portfolio to assess"],
        }

    try:
        # Convert to Decimal dict for engine
        pf = {
            "equity": Decimal(str(portfolio.get("equity", 0))),
            "bond": Decimal(str(portfolio.get("bond", 0))),
            "cash": Decimal(str(portfolio.get("cash", 0))),
        }

        # Run worst historical scenario
        worst = max(HISTORICAL_SCENARIOS, key=lambda s: abs(s.equity_shock or Decimal("0")))
        stress = run_stress_test(pf, worst)

        # Determine risk level from state or default to moderate
        risk_profile = state.get("risk_profile")
        level = risk_profile.level if risk_profile is not None else RiskLevel.MODERATE  # type: ignore[union-attr]

        total = pf["equity"] + pf["bond"] + pf["cash"]
        if total > Decimal("0"):
            eq_pct = int(pf["equity"] / total * 100)
            bd_pct = int(pf["bond"] / total * 100)
            cs_pct = int(pf["cash"] / total * 100)
        else:
            eq_pct = bd_pct = 0
            cs_pct = 100

        health = check_portfolio_health(
            equity_pct=eq_pct,
            bond_pct=bd_pct,
            cash_pct=cs_pct,
            risk_level=level,
            fee_ratio=Decimal("0.010"),
            max_drawdown_pct=abs(stress.loss_pct) * Decimal("100"),
            num_holdings=len(state.get("holdings") or []),
        )

        return {
            "stress_result": stress,
            "health_check": health,
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [f"risk_assessor: {e}"],
        }
