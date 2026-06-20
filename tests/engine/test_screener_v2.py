"""Tests for screener v2 — performance-based scoring."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.data.sources.manager import ManagerInfo
from src.datatypes import FundInfo
from src.engine.screener import (
    score_consistency,
    score_manager,
    score_performance,
    score_risk_control,
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
