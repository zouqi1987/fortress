"""MCP tool: macro regime detection."""
from src.engine.macro_overlay import detect_regime as _detect_regime, get_multiplier
from src.engine.risk_profile import RiskLevel


def detect_regime(
    current: float | None = None,
    ma200: float | None = None,
    ma120: float | None = None,
    risk_level: str = "",
) -> dict:
    """Detect current market regime and optional risk multiplier.

    Compares current index level against 200-day and 120-day moving averages.

    Args:
        current: Current index level (e.g. 上证指数). None → defaults to SIDEWAYS.
        ma200: 200-day moving average.
        ma120: 120-day moving average.
        risk_level: "conservative" | "moderate" | "aggressive" — if provided,
                    also computes the macro adjustment multiplier.

    Returns:
        dict with regime (bull/bear/sideways) and optional multiplier.
    """
    regime = _detect_regime(current, ma200, ma120)

    result: dict = {
        "regime": regime.value,
        "description": _regime_description(regime),
    }

    if risk_level:
        level_map = {
            "conservative": RiskLevel.CONSERVATIVE,
            "moderate": RiskLevel.MODERATE,
            "aggressive": RiskLevel.AGGRESSIVE,
        }
        level = level_map.get(risk_level)
        if level is None:
            return {"error": f"Invalid risk_level: {risk_level!r}. Use 'conservative', 'moderate', or 'aggressive'."}
        multiplier = get_multiplier(regime, level)
        result["multiplier"] = float(multiplier)

    return result


def _regime_description(regime) -> str:
    if regime.value == "bull":
        return "指数 > MA200，牛市周期 — 建议标准配置"
    elif regime.value == "bear":
        return "指数 < MA120，熊市周期 — 建议减配股票、增配债券"
    else:
        return "MA120 < 指数 < MA200，震荡市 — 建议略偏保守"
