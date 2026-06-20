"""MCP tool: portfolio management."""
from decimal import Decimal

from src.engine.allocation import build_allocation, optimize_weights
from src.engine.risk_profile import RiskLevel


def get_allocation(
    risk_level: str,
    total_amount: float,
    fund_returns: dict[str, list[float]] | None = None,
    fund_codes: list[str] | None = None,
) -> dict:
    """Build allocation plan for a given risk level and amount.

    Args:
        risk_level: "conservative" | "moderate" | "aggressive"
        total_amount: total investable amount in CNY
        fund_returns: Optional asset-code → historical returns for weight optimization.
        fund_codes: Optional selected fund codes in priority order.

    When both fund_returns and fund_codes are provided, bucket amounts are split
    among the codes using min-variance optimization instead of equal weight.
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

    buckets = [
        {
            "name": b.name,
            "amount": float(b.amount),
            "fund_type": b.fund_type,
            "layer": b.layer,
        }
        for b in plan.buckets
    ]

    # ── Optional: optimize per-bucket weights ────────────────────────
    optimized_weights = None
    if fund_returns and fund_codes:
        try:
            optimized_weights = {
                c: float(w)
                for c, w in optimize_weights(fund_codes, fund_returns).items()
            }
        except Exception:
            pass  # fallback: leave optimized_weights as None

    result = {
        "equity_pct": plan.equity_pct,
        "bond_pct": plan.bond_pct,
        "cash_pct": plan.cash_pct,
        "total": float(plan.total),
        "buckets": buckets,
    }

    if optimized_weights:
        result["optimized_weights"] = optimized_weights

    return result
