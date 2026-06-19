"""MCP tool: portfolio management."""
from decimal import Decimal

from src.engine.allocation import build_allocation
from src.engine.risk_profile import RiskLevel


def get_allocation(risk_level: str, total_amount: float) -> dict:
    """Build allocation plan for a given risk level and amount.

    Args:
        risk_level: "conservative" | "moderate" | "aggressive"
        total_amount: total investable amount in CNY
    """
    level_map = {
        "conservative": RiskLevel.CONSERVATIVE,
        "moderate": RiskLevel.MODERATE,
        "aggressive": RiskLevel.AGGRESSIVE,
    }
    level = level_map.get(risk_level)
    if level is None:
        return {"error": f"Invalid risk_level: {risk_level!r}. Use 'conservative', 'moderate', or 'aggressive'."}
    plan = build_allocation(level, Decimal(str(total_amount)))

    return {
        "equity_pct": plan.equity_pct,
        "bond_pct": plan.bond_pct,
        "cash_pct": plan.cash_pct,
        "total": float(plan.total),
        "buckets": [
            {
                "name": b.name,
                "amount": float(b.amount),
                "fund_type": b.fund_type,
                "layer": b.layer,
            }
            for b in plan.buckets
        ],
    }
