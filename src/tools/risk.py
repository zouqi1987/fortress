"""MCP tool: risk profile assessment."""
from decimal import Decimal

from src.engine.risk_profile import InvestmentHorizon, assess_risk_profile


def assess_risk(horizon: str, max_loss_pct: float, income: int, experience: int, liquidity: int) -> dict:
    """Run 6-factor risk assessment and return profile.

    Args:
        horizon: questionnaire answer — "A"|"B"|"C"|"D"|"E" (or legacy "short"|"medium"|"long")
        max_loss_pct: max acceptable loss (e.g. 15.0 = 15%)
        income: income stability 1-5
        experience: investment experience 1-5
        liquidity: liquidity need 1-5
    """
    horizon_map = {
        "A": InvestmentHorizon.VERY_SHORT, "very_short": InvestmentHorizon.VERY_SHORT,
        "B": InvestmentHorizon.SHORT, "short": InvestmentHorizon.SHORT,
        "C": InvestmentHorizon.MEDIUM, "medium": InvestmentHorizon.MEDIUM,
        "D": InvestmentHorizon.LONG, "long": InvestmentHorizon.LONG,
        "E": InvestmentHorizon.VERY_LONG, "very_long": InvestmentHorizon.VERY_LONG,
    }
    h = horizon_map.get(horizon)
    if h is None:
        return {"error": f"Invalid horizon: {horizon!r}. Use 'A'|'B'|'C'|'D'|'E' (or 'short'|'medium'|'long'|'very_long')."}

    profile = assess_risk_profile(
        horizon=h,
        max_loss_pct=Decimal(str(max_loss_pct)),
        income_stability=income,
        experience=experience,
        liquidity_need=liquidity,
    )

    return {
        "level": profile.level.value,
        "total_score": profile.total_score,
        "equity_pct": profile.equity_pct,
        "bond_pct": profile.bond_pct,
        "cash_pct": profile.cash_pct,
        "scores": {
            "horizon": profile.scores.horizon,
            "loss_tolerance": profile.scores.loss_tolerance,
            "income_stability": profile.scores.income_stability,
            "experience": profile.scores.experience,
            "liquidity": profile.scores.liquidity,
        },
    }
