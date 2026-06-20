"""Tests for src/engine/allocation.py — three-layer + four-bucket allocation."""
from decimal import Decimal

import pytest

from src.engine.allocation import (
    AllocationLayer,
    AllocationPlan,
    Bucket,
    build_allocation,
)
from src.engine.risk_profile import RiskLevel


class TestBuildAllocation:
    def test_conservative_yields_high_bond_allocation(self):
        plan = build_allocation(RiskLevel.CONSERVATIVE, Decimal("100000"))
        # Conservative should favor fixed-income
        assert plan.cash_pct >= 20
        assert plan.equity_pct <= 20
        assert plan.bond_pct >= 40

    def test_aggressive_yields_high_equity_allocation(self):
        plan = build_allocation(RiskLevel.AGGRESSIVE, Decimal("500000"))
        assert plan.equity_pct >= 60
        assert plan.bond_pct <= 30

    def test_all_percentages_sum_to_100(self):
        for level in RiskLevel:
            plan = build_allocation(level, Decimal("200000"))
            total = plan.cash_pct + plan.bond_pct + plan.equity_pct
            assert total == 100, f"{level}: {total} != 100"

    def test_layers_have_correct_structure(self):
        plan = build_allocation(RiskLevel.MODERATE, Decimal("300000"))
        layer_names = {l.name for l in plan.layers}
        assert "活钱" in layer_names
        assert "稳健" in layer_names
        assert "增值" in layer_names

    def test_buckets_sum_to_total(self):
        total = Decimal("500000")
        plan = build_allocation(RiskLevel.MODERATE, total)
        bucket_sum = sum((b.amount for b in plan.buckets), start=Decimal("0"))
        assert bucket_sum == total

    def test_larger_principal_scales_buckets(self):
        small = build_allocation(RiskLevel.MODERATE, Decimal("100000"))
        large = build_allocation(RiskLevel.MODERATE, Decimal("1_000_000"))
        for sb, lb in zip(small.buckets, large.buckets):
            assert lb.amount > sb.amount

    def test_zero_principal_handled(self):
        plan = build_allocation(RiskLevel.MODERATE, Decimal("0"))
        assert plan.total == Decimal("0")
        assert all(b.amount == Decimal("0") for b in plan.buckets)


class TestOptimizeWeights:
    """Integration test: allocation engine calls optimizer for within-bucket weights."""

    def test_returns_differentiated_weights(self):
        """Optimizer should produce non-equal weights from real return data."""
        from src.engine.allocation import optimize_weights
        import random
        random.seed(42)

        codes = ["safe", "risky", "medium"]
        returns = {
            "safe": [random.gauss(0.0003, 0.005) for _ in range(252)],   # low vol
            "risky": [random.gauss(0.0005, 0.030) for _ in range(252)],  # high vol
            "medium": [random.gauss(0.0004, 0.015) for _ in range(252)], # mid vol
        }
        weights = optimize_weights(codes, returns)
        assert len(weights) == 3
        wl = [float(w) for w in weights.values()]
        assert max(wl) != min(wl), "all equal — optimizer not producing differentiated weights"
        # Safe asset should get more weight in min-variance
        assert float(weights["safe"]) > float(weights["risky"]), (
            f"safe={float(weights['safe']):.2%} should > risky={float(weights['risky']):.2%}"
        )
        assert 0.99 < sum(wl) < 1.01

    def test_fallback_on_empty_returns(self):
        """Empty returns → equal weight fallback."""
        from src.engine.allocation import optimize_weights
        weights = optimize_weights(["A", "B"], {})
        assert weights == {"A": Decimal("0.5"), "B": Decimal("0.5")}

    def test_respects_max_weight(self):
        """All weights within configured max."""
        from src.engine.allocation import optimize_weights
        import random
        random.seed(99)
        codes = [f"F{i}" for i in range(5)]
        returns = {c: [random.gauss(0.0005, 0.02) for _ in range(252)] for c in codes}
        weights = optimize_weights(codes, returns, max_weight=Decimal("0.40"))
        for code, w in weights.items():
            assert float(w) <= 0.41, f"{code}={float(w):.3f} exceeds max"
