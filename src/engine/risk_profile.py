"""5-factor risk profile assessment engine.

Zero I/O — pure function that maps questionnaire answers to a RiskProfile.
All inputs are scalars; all outputs are computed deterministically.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class InvestmentHorizon(Enum):
    SHORT = "short"    # ≤1 year
    MEDIUM = "medium"  # 1–3 years
    LONG = "long"      # ≥3 years


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class RiskScore:
    """Per-factor scores, each 0–20. Total = sum, 0–100."""

    horizon: int
    loss_tolerance: int
    income_stability: int
    experience: int
    liquidity: int

    @property
    def total(self) -> int:
        return self.horizon + self.loss_tolerance + self.income_stability + self.experience + self.liquidity


@dataclass(frozen=True)
class RiskProfile:
    """Complete risk assessment result."""

    level: RiskLevel
    scores: RiskScore
    total_score: int
    equity_pct: int
    bond_pct: int
    cash_pct: int


def assess_risk_profile(
    horizon: InvestmentHorizon,
    max_loss_pct: Decimal,
    income_stability: int,
    experience: int,
    liquidity_need: int,
) -> RiskProfile:
    """Run the 5-factor risk assessment.

    Args:
        horizon: Investment time horizon.
        max_loss_pct: Maximum acceptable drawdown (e.g. Decimal("15") = 15%).
        income_stability: 1 (unstable) to 5 (very stable).
        experience: 1 (novice) to 5 (professional).
        liquidity_need: 1 (low need, can lock up) to 5 (high need, must stay liquid).

    Returns:
        RiskProfile with level, per-factor scores, and suggested allocation.
    """
    # ── Horizon: 0–20 ───────────────────────────────────────────────
    if horizon == InvestmentHorizon.LONG:
        horizon_score = 18
    elif horizon == InvestmentHorizon.MEDIUM:
        horizon_score = 10
    else:
        horizon_score = 3

    # ── Loss tolerance: 0–20 ────────────────────────────────────────
    if max_loss_pct >= Decimal("25"):
        loss_score = 18
    elif max_loss_pct >= Decimal("15"):
        loss_score = 12
    elif max_loss_pct >= Decimal("10"):
        loss_score = 8
    else:
        loss_score = 3

    # ── Income stability: 1–5 → 0–20 ───────────────────────────────
    income_score = max(1, min(20, (income_stability - 1) * 5))

    # ── Experience: 1–5 → 0–20 ─────────────────────────────────────
    exp_score = max(1, min(20, (experience - 1) * 5))

    # ── Liquidity need: 1–5 → 0–20 (inverse: high need = low risk) ─
    liq_score = max(1, min(20, (5 - liquidity_need) * 5))

    scores = RiskScore(
        horizon=horizon_score,
        loss_tolerance=loss_score,
        income_stability=income_score,
        experience=exp_score,
        liquidity=liq_score,
    )
    total = scores.total

    # ── Risk level ──────────────────────────────────────────────────
    if total >= 70:
        level = RiskLevel.AGGRESSIVE
    elif total >= 30:
        level = RiskLevel.MODERATE
    else:
        level = RiskLevel.CONSERVATIVE

    # ── Allocation hint ─────────────────────────────────────────────
    equity, bond, cash = _allocation_from_score(total)

    return RiskProfile(
        level=level,
        scores=scores,
        total_score=total,
        equity_pct=equity,
        bond_pct=bond,
        cash_pct=cash,
    )


def _allocation_from_score(total: int) -> tuple[int, int, int]:
    """Map risk score to equity/bond/cash percentages."""
    if total >= 70:
        return (80, 15, 5)
    elif total >= 50:
        return (60, 30, 10)
    elif total >= 30:
        return (40, 50, 10)
    else:
        return (10, 60, 30)
