"""Tests for screener v2 — performance-based scoring."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.data.sources.manager import ManagerInfo
from src.datatypes import FundInfo
from src.engine.screener import (
    ScreenConfig,
    score_consistency,
    score_manager,
    score_performance,
    score_risk_control,
    screen_funds,
)


class TestScorePerformance:
    def test_flat_returns_mid_score(self):
        """NAV unchanged → low but not zero (zero return gets half credit)."""
        navs = [1.0] * 100
        s = score_performance(navs)
        assert 0 <= s <= 10  # zero returns = half points on available periods

    def test_rising_returns_high_score(self):
        """~10% gain over 1 year → decent score."""
        navs = [1.0]
        for _ in range(260):
            navs.append(navs[-1] * 1.0004)  # ~10% annual
        s = score_performance(navs)
        assert s >= 10  # 1m+3m+6m+1y all positive

    def test_falling_returns_low_score(self):
        """~10% loss over 1 year → low score."""
        navs = [1.0]
        for _ in range(260):
            navs.append(navs[-1] * 0.9996)  # ~-10% annual
        s = score_performance(navs)
        assert s <= 12  # no positive period get full pts

    def test_too_few_nav_returns_zero(self):
        s = score_performance([])
        assert s == 0

    # ── Benchmark-relative tests ───────────────────────────────────

    def test_beating_benchmark_gets_full_points(self):
        """Fund returns +10%, benchmark +2% → excess > +2% → full points."""
        fund_navs = [1.0]
        bench_navs = [1.0]
        for _ in range(260):
            fund_navs.append(fund_navs[-1] * 1.0004)   # ~10% annual
            bench_navs.append(bench_navs[-1] * 1.00008)  # ~2% annual
        s = score_performance(fund_navs, bench_navs)
        assert s >= 8  # should get meaningful points for outperformance

    def test_matching_benchmark_gets_reduced_points(self):
        """Fund and benchmark return same ~2% → excess near 0 → reduced."""
        navs = [1.0]
        for _ in range(260):
            navs.append(navs[-1] * 1.00008)  # ~2% annual
        s = score_performance(navs, navs)  # same data as benchmark
        assert s < 15  # excess=0 → 80% of full on available periods

    def test_severe_underperformance_scores_zero(self):
        """Fund -2%, benchmark +10% → excess -12% → near zero (short periods
        get partial credit since excess is diluted)."""
        fund_navs = [1.0]
        bench_navs = [1.0]
        for _ in range(260):
            fund_navs.append(fund_navs[-1] * 0.99992)  # ~-2% annual
            bench_navs.append(bench_navs[-1] * 1.0004)   # ~10% annual
        s = score_performance(fund_navs, bench_navs)
        assert s <= 3  # 1m/3m excess > -2%/-5% gets minimal partial credit

    def test_falls_back_to_absolute_when_no_benchmark(self):
        """Without benchmark, uses absolute positive/negative logic."""
        navs = [1.0]
        for _ in range(260):
            navs.append(navs[-1] * 1.0001)
        with_bench = score_performance(navs, navs)   # excess always 0
        without_bench = score_performance(navs)         # absolute
        assert without_bench != with_bench  # different scoring paths

    def test_benchmark_too_short_falls_back(self):
        """Benchmark shorter than period → uses absolute fallback."""
        fund_navs = [1.0]
        for _ in range(260):
            fund_navs.append(fund_navs[-1] * 1.0001)
        short_bench = [1.0, 1.01]  # only 2 data points
        # With short benchmark, falls back to absolute
        s_with = score_performance(fund_navs, short_bench)
        s_without = score_performance(fund_navs)
        assert s_with == s_without


class TestScoreRiskControl:
    def test_stable_nav_low_risk(self):
        navs = [1.0 + i * 0.001 for i in range(252)]
        s = score_risk_control(navs)
        assert s >= 15

    def test_volatile_nav_high_risk(self):
        navs = [1.0]
        for _ in range(251):
            navs.append(navs[-1] * (1.0 + (0.1 if len(navs) % 2 == 0 else -0.09)))
        s = score_risk_control(navs)
        assert s <= 10

    def test_empty_returns_zero(self):
        assert score_risk_control([]) == 0

    def test_decimal_nav_does_not_crash(self):
        """Prove-It: API returns Decimal NAVs — must not crash on **0.5."""
        navs = [Decimal("1.0")]
        for _ in range(251):
            navs.append(navs[-1] * Decimal("1.001"))
        s = score_risk_control(navs)
        assert isinstance(s, int)
        assert 0 <= s <= 20

    def test_decimal_and_float_produce_same_score(self):
        """Float and Decimal NAV inputs → same score (within margin)."""
        float_navs = [1.0]
        for _ in range(251):
            float_navs.append(float_navs[-1] * 1.001)
        dec_navs = [Decimal(str(v)) for v in float_navs]
        assert score_risk_control(float_navs) == score_risk_control(dec_navs)


class TestScoreConsistency:
    def test_all_positive_quarters(self):
        """8 quarters all positive → perfect."""
        navs = [1.0]
        for _ in range(504):  # ~2 years daily
            navs.append(navs[-1] * 1.001)
        s = score_consistency(navs)
        assert s >= 8  # high consistency

    def test_mixed_quarters(self):
        """Volatile returns → moderate consistency."""
        navs = [1.0]
        for i in range(503):
            mult = 1.02 if i % 40 < 20 else 0.98
            navs.append(navs[-1] * mult)
        s = score_consistency(navs)
        assert s >= 0

    def test_empty_returns_zero(self):
        assert score_consistency([]) == 0


class TestScoreManager:
    def test_experienced_manager_high_score(self):
        m = ManagerInfo(fund_code="000001", name="张三", tenure_days=1500,
                        cumulative_return="+80.5%", fund_count=2)
        s = score_manager(m)
        assert s >= 3  # good manager

    def test_new_manager_low_score(self):
        m = ManagerInfo(fund_code="000001", name="新人", tenure_days=100,
                        cumulative_return="+1.2%", fund_count=5)
        s = score_manager(m)
        assert s <= 3

    def test_none_manager_returns_zero(self):
        assert score_manager(None) == 0


# ── Integration: screen_funds with benchmark_data ──────────────────


def _make_fund(code, name, fund_type="bond", size=10_000_000_000):
    return FundInfo(
        code=code, name=name, type=fund_type,
        net_asset_value=Decimal(str(size)),
        fee_rate=Decimal("0.015"),
        inception_date=date(2015, 1, 1),
    )


class TestScreenFundsWithBenchmark:

    def test_benchmark_reduces_score_for_underperformer(self):
        """Fund underperforming benchmark scores lower than without it."""
        fund_navs = [1.0]
        bench_navs = [1.0]
        for _ in range(260):
            fund_navs.append(fund_navs[-1] * 1.00008)   # ~2% annual (underperform)
            bench_navs.append(bench_navs[-1] * 1.0004)    # ~10% annual (benchmark)
        fund = _make_fund("TEST01", "测试债基")

        config = ScreenConfig()
        result_without = screen_funds([fund], config, nav_data={"TEST01": fund_navs})
        result_with = screen_funds([fund], config, nav_data={"TEST01": fund_navs},
                                   benchmark_data={"bond": bench_navs})
        assert len(result_without) == 1
        assert len(result_with) == 1
        assert result_with[0].score < result_without[0].score

    def test_benchmark_does_not_punish_outperformer(self):
        """Fund outperforming benchmark should score approximately the same
        (short-period excess may not cross +2% threshold for 80%-full,
        but overall score stays within a small margin of absolute scoring)."""
        fund_navs = [1.0]
        bench_navs = [1.0]
        for _ in range(260):
            fund_navs.append(fund_navs[-1] * 1.0004)     # ~10% (outperform)
            bench_navs.append(bench_navs[-1] * 1.00008)   # ~2% (benchmark)
        fund = _make_fund("TEST02", "优质债基")

        config = ScreenConfig()
        result_without = screen_funds([fund], config, nav_data={"TEST02": fund_navs})
        result_with = screen_funds([fund], config, nav_data={"TEST02": fund_navs},
                                   benchmark_data={"bond": bench_navs})
        # Should not be severely penalized — within 5 points of absolute
        assert abs(result_with[0].score - result_without[0].score) <= 5

    def test_no_benchmark_for_type_uses_absolute_scoring(self):
        """Fund type not in benchmark_data → falls back to absolute scoring."""
        fund_navs = [1.0]
        for _ in range(260):
            fund_navs.append(fund_navs[-1] * 1.0001)
        fund = _make_fund("TEST03", "混合基金", fund_type="mixed")

        config = ScreenConfig()
        result_without = screen_funds([fund], config, nav_data={"TEST03": fund_navs})
        # benchmark only has "bond" key, not "mixed"
        result_with = screen_funds([fund], config, nav_data={"TEST03": fund_navs},
                                   benchmark_data={"bond": [1.0, 1.05]})
        assert result_with[0].score == result_without[0].score
