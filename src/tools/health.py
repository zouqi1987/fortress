"""MCP tool: portfolio health checking."""
from decimal import Decimal

from src.engine.health_checker import check_portfolio_health
from src.engine.risk_profile import RiskLevel


def check_health(
    equity_pct: int,
    bond_pct: int,
    cash_pct: int,
    risk_level: str,
    fee_ratio: float,
    max_drawdown_pct: float,
    num_holdings: int,
) -> dict:
    """Score portfolio health across four dimensions.

    Args:
        equity_pct/bond_pct/cash_pct: Current allocation percentages (must sum to 100).
        risk_level: "conservative" | "moderate" | "aggressive"
        fee_ratio: Weighted average expense ratio (e.g. 0.012 = 1.2%).
        max_drawdown_pct: Recent maximum drawdown (e.g. 15.0 = 15%).
        num_holdings: Number of fund holdings.
    """
    level_map = {
        "conservative": RiskLevel.CONSERVATIVE,
        "moderate": RiskLevel.MODERATE,
        "aggressive": RiskLevel.AGGRESSIVE,
    }
    level = level_map.get(risk_level)
    if level is None:
        return {"error": f"Invalid risk_level: {risk_level!r}. Use 'conservative', 'moderate', or 'aggressive'."}

    result = check_portfolio_health(
        equity_pct=equity_pct,
        bond_pct=bond_pct,
        cash_pct=cash_pct,
        risk_level=level,
        fee_ratio=Decimal(str(fee_ratio)),
        max_drawdown_pct=Decimal(str(max_drawdown_pct)),
        num_holdings=num_holdings,
    )

    return {
        "overall_score": result.overall_score,
        "grade": result.grade,
        "drift_score": result.drift_score,
        "diversification_score": result.diversification_score,
        "fee_score": result.fee_score,
        "drawdown_score": result.drawdown_score,
        "warnings": list(result.warnings),
    }
