"""Macro overlay — independent risk multiplier based on market regime.

Does NOT modify fund scores. Applied as a multiplier to asset allocation
recommendations after screening. Market regime is determined by comparing
current index level against moving averages (200-day, 120-day).

Rules:
  BULL:    price > MA200 → multiplier 1.0 (no adjustment)
  SIDEWAYS: MA120 < price < MA200 → 0.8 (slightly conservative)
  BEAR:    price < MA120 → 0.6 (conservative, favor bonds)
"""
from decimal import Decimal
from enum import Enum

from src.engine.risk_profile import RiskLevel


class MarketRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"


def detect_regime(
    current: float | None = None,
    ma200: float | None = None,
    ma120: float | None = None,
) -> MarketRegime:
    """Detect current market regime from index vs moving averages.

    If data is unavailable, defaults to SIDEWAYS (most conservative default).

    Args:
        current: Current index level (e.g. 上证指数)
        ma200: 200-day moving average
        ma120: 120-day moving average

    Returns:
        MarketRegime enum.
    """
    if current is None or ma200 is None or ma120 is None:
        # No data → assume sideways (conservative default)
        return MarketRegime.SIDEWAYS

    if current > ma200:
        return MarketRegime.BULL
    elif current < ma120:
        return MarketRegime.BEAR
    else:
        return MarketRegime.SIDEWAYS


def get_multiplier(regime: MarketRegime, risk_level: RiskLevel) -> Decimal:
    """Get macro adjustment multiplier for a given regime and risk level.

    Conservative investors are less impacted by bear markets (already
    have more bonds). Aggressive investors should reduce more in bears.

    Args:
        regime: Current market regime.
        risk_level: Investor's risk tolerance.

    Returns:
        Multiplier 0.0-1.0 applied to asset allocation recommendations.
    """
    base = {
        MarketRegime.BULL: Decimal("1.0"),
        MarketRegime.SIDEWAYS: Decimal("0.8"),
        MarketRegime.BEAR: Decimal("0.6"),
    }[regime]

    # Conservative investors in bear: slightly less impact (already safe)
    if regime == MarketRegime.BEAR and risk_level == RiskLevel.CONSERVATIVE:
        return Decimal("0.7")

    return base
