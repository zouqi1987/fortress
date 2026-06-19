"""Allocator node — runs allocation, screening, and optimization.

Pure function: (state) → state_update dict.
Active on paths A and B.
"""
from decimal import Decimal

from src.agent.state import ConversationState
from src.engine.allocation import build_allocation
from src.engine.risk_profile import RiskLevel


def allocator_node(state: ConversationState) -> dict:
    """Build allocation plan from risk profile.

    Requires risk_profile in state. Returns allocation_plan and audit_results.
    """
    risk_profile = state.get("risk_profile")

    if risk_profile is None:
        return {
            "errors": state.get("errors", []) + ["allocator: no risk profile available"],
        }

    try:
        level = risk_profile.level  # type: ignore[union-attr]
        pf = state.get("portfolio") or {}
        total = (Decimal(str(pf.get("equity", 0) or 0))
               + Decimal(str(pf.get("bond", 0) or 0))
               + Decimal(str(pf.get("cash", 0) or 0)))

        # Default 10万 for scenario planning when no actual portfolio exists
        if total == Decimal("0"):
            total = Decimal("100000")

        plan = build_allocation(level, total)

        return {
            "allocation_plan": plan,
            "audit_results": [],  # populated by full pipeline
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [f"allocator: {e}"],
        }
