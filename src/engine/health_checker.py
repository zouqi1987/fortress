"""Portfolio health scoring engine.

Zero I/O. Takes portfolio metrics, returns health grade with dimension scores.
"""
from dataclasses import dataclass
from decimal import Decimal

from src.engine.risk_profile import RiskLevel

# ── Target allocations by risk level ─────────────────────────────────

# Health-check targets: what we score against.
# These are intentionally close to, but not identical to,
# risk_profile._allocation_from_score which maps score ranges:
#   conservative: (10, 60, 30)  moderate 30-49: (40, 50, 10)  moderate 50-69: (60, 30, 10)  aggressive: (80, 15, 5)
# Health targets pick the conservative end of each range to encourage discipline.
_TARGETS = {
    RiskLevel.CONSERVATIVE: (10, 60, 30),
    RiskLevel.MODERATE: (50, 40, 10),
    RiskLevel.AGGRESSIVE: (75, 20, 5),
}

_OPTIMAL_HOLDINGS_RANGE = (4, 8)  # ideal number of fund holdings
_MAX_HOLDINGS = 15  # above this gets penalized heavily


@dataclass(frozen=True)
class HealthCheckResult:
    """Portfolio health assessment."""

    overall_score: int  # 0–100
    grade: str  # "A" / "B" / "C" / "D" / "F"
    drift_score: int  # how well allocation matches risk target
    diversification_score: int  # number of holdings, concentration
    fee_score: int  # weighted fee ratio
    drawdown_score: int  # recent drawdown severity
    warnings: tuple[str, ...]


def check_portfolio_health(
    equity_pct: int,
    bond_pct: int,
    cash_pct: int,
    risk_level: RiskLevel,
    fee_ratio: Decimal,
    max_drawdown_pct: Decimal,
    num_holdings: int,
) -> HealthCheckResult:
    """Score portfolio health across four dimensions.

    Args:
        equity_pct/bond_pct/cash_pct: Current allocation percentages.
        risk_level: Investor's risk tolerance.
        fee_ratio: Weighted average expense ratio (e.g., 0.012 = 1.2%).
        max_drawdown_pct: Recent maximum drawdown (e.g., 15 = 15%).
        num_holdings: Number of fund holdings.

    Returns:
        HealthCheckResult with overall score, grade, and dimension scores.
    """
    warnings: list[str] = []

    # ── 1. Allocation drift (0–35) ──────────────────────────────────
    target_eq, target_bond, target_cash = _TARGETS[risk_level]
    drift = abs(equity_pct - target_eq) + abs(bond_pct - target_bond) + abs(cash_pct - target_cash)
    drift_score = max(0, 35 - drift // 2)

    if drift > 20:
        warnings.append(f"资产配置偏离目标较大 (偏离度 {drift}%)")

    # ── 2. Diversification (0–30) ────────────────────────────────────
    if _OPTIMAL_HOLDINGS_RANGE[0] <= num_holdings <= _OPTIMAL_HOLDINGS_RANGE[1]:
        div_score = 30
    elif num_holdings < _OPTIMAL_HOLDINGS_RANGE[0]:
        div_score = 15 + num_holdings * 3  # <4 holdings = penalty
        warnings.append(f"持仓数量过少 ({num_holdings}只)，集中度风险较高")
    elif num_holdings <= _MAX_HOLDINGS:
        div_score = 30 - (num_holdings - _OPTIMAL_HOLDINGS_RANGE[1]) * 3
    else:
        div_score = 5
        warnings.append(f"持仓数量过多 ({num_holdings}只)，过度分散降低收益")

    # ── 3. Fee efficiency (0–25) ─────────────────────────────────────
    if fee_ratio <= Decimal("0.005"):
        fee_score = 25
    elif fee_ratio <= Decimal("0.010"):
        fee_score = 20
    elif fee_ratio <= Decimal("0.015"):
        fee_score = 15
    elif fee_ratio <= Decimal("0.020"):
        fee_score = 10
    else:
        fee_score = 5
        warnings.append(f"加权费率偏高 ({float(fee_ratio):.2%})")

    # ── 4. Drawdown (0–10) ──────────────────────────────────────────
    if max_drawdown_pct <= Decimal("5"):
        dd_score = 10
    elif max_drawdown_pct <= Decimal("10"):
        dd_score = 8
    elif max_drawdown_pct <= Decimal("20"):
        dd_score = 5
    elif max_drawdown_pct <= Decimal("30"):
        dd_score = 2
    else:
        dd_score = 0
        warnings.append(f"近期最大回撤较大 ({float(max_drawdown_pct):.0f}%)")

    overall = drift_score + div_score + fee_score + dd_score

    # ── Grade ────────────────────────────────────────────────────────
    if overall >= 80:
        grade = "A"
    elif overall >= 60:
        grade = "B"
    elif overall >= 40:
        grade = "C"
    elif overall >= 20:
        grade = "D"
    else:
        grade = "F"

    return HealthCheckResult(
        overall_score=overall,
        grade=grade,
        drift_score=drift_score,
        diversification_score=div_score,
        fee_score=fee_score,
        drawdown_score=dd_score,
        warnings=tuple(warnings),
    )
