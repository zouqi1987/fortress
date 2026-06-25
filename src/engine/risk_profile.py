"""6-factor risk profile assessment engine with consistency checks.

Zero I/O — pure functions.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class InvestmentHorizon(Enum):
    VERY_SHORT = "very_short"  # ≤1 year (A)
    SHORT = "short"            # 1–2 years (B)
    MEDIUM = "medium"          # 2–3 years (C)
    LONG = "long"              # 3–5 years (D)
    VERY_LONG = "very_long"    # ≥5 years (E)


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class RiskScore:
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
    level: RiskLevel
    scores: RiskScore
    total_score: int
    equity_pct: int
    bond_pct: int
    cash_pct: int
    expected_return_pct: Decimal | None = None
    realistic_return_low: Decimal | None = None
    realistic_return_high: Decimal | None = None
    is_expectation_realistic: bool | None = None
    warnings: tuple[str, ...] = ()  # consistency warnings
    product_weight_bias: str = "balanced"  # "growth" | "balanced" | "safety"


def assess_risk_profile(
    horizon: InvestmentHorizon,
    max_loss_pct: Decimal,
    income_stability: int,
    experience: int,
    liquidity_need: int,
    expected_return_pct: Decimal | None = None,
) -> RiskProfile:
    """Run the 6-factor risk assessment with consistency checks."""
    warnings: list[str] = []

    # ── Scoring ─────────────────────────────────────────────────────
    # Horizon (5 levels: VERY_SHORT=2, SHORT=6, MEDIUM=10, LONG=14, VERY_LONG=18)
    if horizon == InvestmentHorizon.VERY_LONG:
        horizon_score = 18
    elif horizon == InvestmentHorizon.LONG:
        horizon_score = 14
    elif horizon == InvestmentHorizon.MEDIUM:
        horizon_score = 10
    elif horizon == InvestmentHorizon.SHORT:
        horizon_score = 6
    else:
        horizon_score = 2

    # Loss tolerance
    loss = float(max_loss_pct)
    if loss >= 25:
        loss_score = 18
    elif loss >= 15:
        loss_score = 12
    elif loss >= 10:
        loss_score = 8
    else:
        loss_score = 3

    income_score = max(1, min(20, (income_stability - 1) * 5))
    exp_score = max(1, min(20, (experience - 1) * 5))
    liq_score = max(1, min(20, (5 - liquidity_need) * 5))

    scores = RiskScore(horizon_score, loss_score, income_score, exp_score, liq_score)
    total = scores.total

    # ── Risk level ──────────────────────────────────────────────────
    if total >= 70:
        level = RiskLevel.AGGRESSIVE
    elif total >= 30:
        level = RiskLevel.MODERATE
    else:
        level = RiskLevel.CONSERVATIVE

    # ── Consistency checks ──────────────────────────────────────────
    product_bias = "balanced"

    # 1. High return + low risk = impossible
    if expected_return_pct is not None and max_loss_pct is not None:
        exp_ret = float(expected_return_pct)
        max_loss = float(max_loss_pct)
        if exp_ret > 10 and max_loss < 10:
            warnings.append(
                f"⚠️ 期望收益 {exp_ret:.0f}% 但只接受 {max_loss:.0f}% 亏损 — "
                "高收益必然伴随高风险，这个组合现实中几乎不存在"
            )
            product_bias = "safety"  # err on side of safety
        if exp_ret < 4 and max_loss > 15:
            warnings.append(
                f"💡 你能承受 {max_loss:.0f}% 回撤但只期望 {exp_ret:.0f}% 收益 — "
                "可以考虑稍微提高收益目标，你的风险承受力支持更高收益"
            )
            product_bias = "growth"  # user can afford more growth

    # 2. Short horizon + aggressive = dangerous
    if horizon in (InvestmentHorizon.VERY_SHORT, InvestmentHorizon.SHORT) and level == RiskLevel.AGGRESSIVE:
        warnings.append(
            "⚠️ 投资期限不到2年但风险偏好激进 — 短期市场波动可能让你来不及回本"
        )
        if level != RiskLevel.CONSERVATIVE:
            level = RiskLevel.MODERATE  # auto-downshift
            product_bias = "safety"

    # 3. Novice + aggressive = risky
    if experience <= 2 and level == RiskLevel.AGGRESSIVE:
        warnings.append(
            "⚠️ 投资经验较少但风险偏好激进 — 建议先从稳健型开始，积累经验后再加仓"
        )
        product_bias = "balanced"

    # 4. High liquidity + long horizon = contradictory
    if liquidity_need >= 4 and horizon in (InvestmentHorizon.LONG, InvestmentHorizon.VERY_LONG):
        warnings.append(
            "⚠️ 既想长期投资又需要高流动性 — 建议预留 6 个月生活费在货币基金，其余再长期配置"
        )

    # 5. Conservative + high return expectation = unrealistic
    if level == RiskLevel.CONSERVATIVE and expected_return_pct is not None:
        if float(expected_return_pct) > 6:
            warnings.append(
                f"⚠️ 保守型配置通常只能实现 2-6% 年化，你的目标 {float(expected_return_pct):.0f}% 可能无法达成"
            )
            product_bias = "growth"  # need more growth to hit target

    # ── Allocation ──────────────────────────────────────────────────
    equity, bond, cash = _allocation_from_score(total)

    # ── Apply product bias to allocation ────────────────────────────
    if product_bias == "growth" and equity < 50:
        equity, bond, cash = (60, 30, 10)
    elif product_bias == "safety" and equity > 40:
        equity, bond, cash = (30, 55, 15)

    # ── Reality check ───────────────────────────────────────────────
    realistic_low: Decimal | None = None
    realistic_high: Decimal | None = None
    is_realistic: bool | None = None

    if expected_return_pct is not None:
        _return_ranges = {
            RiskLevel.CONSERVATIVE: (Decimal("0.02"), Decimal("0.06")),
            RiskLevel.MODERATE: (Decimal("0.04"), Decimal("0.12")),
            RiskLevel.AGGRESSIVE: (Decimal("0.06"), Decimal("0.20")),
        }
        low, high = _return_ranges[level]
        realistic_low = low
        realistic_high = high
        is_realistic = low <= expected_return_pct / Decimal("100") <= high

    return RiskProfile(
        level=level, scores=scores, total_score=total,
        equity_pct=equity, bond_pct=bond, cash_pct=cash,
        expected_return_pct=expected_return_pct,
        realistic_return_low=realistic_low, realistic_return_high=realistic_high,
        is_expectation_realistic=is_realistic,
        warnings=tuple(warnings),
        product_weight_bias=product_bias,
    )


def _allocation_from_score(total: int) -> tuple[int, int, int]:
    if total >= 70:   return (80, 15, 5)
    elif total >= 50: return (60, 30, 10)
    elif total >= 30: return (40, 50, 10)
    else:             return (10, 60, 30)
