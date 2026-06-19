"""Three-layer + four-bucket allocation engine.

Zero I/O. Takes risk level + total principal, returns structured allocation plan.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from src.engine.risk_profile import RiskLevel


@dataclass(frozen=True)
class AllocationLayer:
    """One of three layers: 活钱 / 稳健 / 增值."""

    name: str
    equity_pct: int
    bond_pct: int
    cash_pct: int
    description: str = ""


@dataclass(frozen=True)
class Bucket:
    """A concrete allocation bucket with target amount."""

    name: str
    amount: Decimal
    fund_type: str  # "money" | "bond" | "mixed" | "index" | "stock"
    layer: str  # which layer this bucket belongs to


@dataclass(frozen=True)
class AllocationPlan:
    """Complete allocation plan for a given risk level and principal."""

    layers: tuple[AllocationLayer, ...]
    layer_weights: tuple[Decimal, ...]  # matching layers, sum=1
    buckets: tuple[Bucket, ...]
    total: Decimal

    @property
    def equity_pct(self) -> int:
        """Weighted average equity percentage across layers."""
        val = float(sum(
            Decimal(l.equity_pct) * w
            for l, w in zip(self.layers, self.layer_weights)
        ))
        return round(val)

    @property
    def bond_pct(self) -> int:
        val = float(sum(
            Decimal(l.bond_pct) * w
            for l, w in zip(self.layers, self.layer_weights)
        ))
        return round(val)

    @property
    def cash_pct(self) -> int:
        # Ensure sum = 100
        return 100 - self.equity_pct - self.bond_pct


# ── Layer definitions by risk level ──────────────────────────────────

_LAYER_ALLOCATIONS = {
    RiskLevel.CONSERVATIVE: (
        AllocationLayer("活钱", 0, 10, 90, "日常开销，随时可取"),
        AllocationLayer("稳健", 10, 70, 20, "保本为主，稳健增值"),
        AllocationLayer("增值", 20, 60, 20, "长期增值，承受有限波动"),
    ),
    RiskLevel.MODERATE: (
        AllocationLayer("活钱", 0, 20, 80, "6个月生活备用金"),
        AllocationLayer("稳健", 30, 60, 10, "核心资产，攻守兼备"),
        AllocationLayer("增值", 70, 25, 5, "长期增值，承受适度波动"),
    ),
    RiskLevel.AGGRESSIVE: (
        AllocationLayer("活钱", 0, 30, 70, "3个月生活备用金"),
        AllocationLayer("稳健", 50, 40, 10, "配置底仓，降低波动"),
        AllocationLayer("增值", 85, 10, 5, "追求长期高收益"),
    ),
}


def build_allocation(risk_level: RiskLevel, total_principal: Decimal) -> AllocationPlan:
    """Build a complete allocation plan.

    Args:
        risk_level: Risk tolerance from 5-factor assessment.
        total_principal: Total investable amount in CNY.

    Returns:
        AllocationPlan with layers, buckets, and target amounts.
    """
    layers = _LAYER_ALLOCATIONS[risk_level]

    # Layer weight distribution varies by risk level
    if risk_level == RiskLevel.CONSERVATIVE:
        layer_weights = (Decimal("0.30"), Decimal("0.50"), Decimal("0.20"))
    elif risk_level == RiskLevel.MODERATE:
        layer_weights = (Decimal("0.20"), Decimal("0.45"), Decimal("0.35"))
    else:
        layer_weights = (Decimal("0.10"), Decimal("0.35"), Decimal("0.55"))

    buckets: list[Bucket] = []
    bucket_id = 0

    for layer, weight in zip(layers, layer_weights):
        layer_amount = (total_principal * weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 活钱 → money market
        if layer.name == "活钱":
            buckets.append(Bucket(
                name=f"{layer.name}-货币基金",
                amount=layer_amount,
                fund_type="money",
                layer=layer.name,
            ))
        # 稳健 → mostly bond, some mixed
        elif layer.name == "稳健":
            bond_amt = (layer_amount * Decimal(str(layer.bond_pct / 100))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            mixed_amt = layer_amount - bond_amt
            if bond_amt > 0:
                buckets.append(Bucket(
                    name=f"{layer.name}-债券基金",
                    amount=bond_amt,
                    fund_type="bond",
                    layer=layer.name,
                ))
            if mixed_amt > 0:
                buckets.append(Bucket(
                    name=f"{layer.name}-混合基金",
                    amount=mixed_amt,
                    fund_type="mixed",
                    layer=layer.name,
                ))
        # 增值 → mostly equity/index, some bond
        else:
            equity_amt = (layer_amount * Decimal(str(layer.equity_pct / 100))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            bond_amt = layer_amount - equity_amt
            if equity_amt > 0:
                buckets.append(Bucket(
                    name=f"{layer.name}-指数基金",
                    amount=equity_amt,
                    fund_type="index",
                    layer=layer.name,
                ))
            if bond_amt > 0:
                buckets.append(Bucket(
                    name=f"{layer.name}-债券基金",
                    amount=bond_amt,
                    fund_type="bond",
                    layer=layer.name,
                ))

    return AllocationPlan(
        layers=layers,
        layer_weights=layer_weights,
        buckets=tuple(buckets),
        total=total_principal,
    )
