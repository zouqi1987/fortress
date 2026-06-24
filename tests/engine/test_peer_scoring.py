"""Tests for peer-relative scoring — score_peer_performance().

Zero I/O pure function: takes fund returns + category averages, returns 0-100
score where 50 = peer average. Linear mapping with clamp to [0, 100].
"""
import pytest

from src.datatypes import InsufficientDataError
from src.engine.peer_scoring import (
    PERIOD_WEIGHTS,
    score_peer_performance,
)


def _full_returns(**overrides):
    """Return a 5-period returns dict, defaults all 0.0, overrides apply."""
    base = {"ret_1m": 0.0, "ret_3m": 0.0, "ret_6m": 0.0, "ret_1y": 0.0, "ret_3y": 0.0}
    base.update(overrides)
    return base


class TestScorePeerPerformance:
    def test_at_peer_average_scores_50(self):
        """Fund returns == category averages → weighted_excess 0 → score 50."""
        fund = _full_returns(ret_1m=1.2, ret_3m=3.1, ret_6m=5.0, ret_1y=8.0, ret_3y=15.0)
        cat = _full_returns(ret_1m=1.2, ret_3m=3.1, ret_6m=5.0, ret_1y=8.0, ret_3y=15.0)
        assert score_peer_performance(fund, cat) == 50

    def test_outperforms_peers_scores_above_50(self):
        """Fund beats category in every period → score > 50."""
        fund = _full_returns(ret_1m=2.0, ret_3m=4.0, ret_6m=7.0, ret_1y=12.0, ret_3y=20.0)
        cat = _full_returns(ret_1m=1.0, ret_3m=2.0, ret_6m=4.0, ret_1y=8.0, ret_3y=15.0)
        assert score_peer_performance(fund, cat) > 50

    def test_underperforms_peers_scores_below_50(self):
        """Fund lags category in every period → score < 50."""
        fund = _full_returns(ret_1m=0.0, ret_3m=1.0, ret_6m=2.0, ret_1y=4.0, ret_3y=10.0)
        cat = _full_returns(ret_1m=1.0, ret_3m=2.0, ret_6m=4.0, ret_1y=8.0, ret_3y=15.0)
        assert score_peer_performance(fund, cat) < 50

    def test_plus_10pp_weighted_excess_scores_70(self):
        """+10pp excess in every period → weighted_excess=10 → 50 + 10*2 = 70.

        Sum of weights is 1.0, so uniform +10pp excess → 10pp weighted excess.
        """
        fund = _full_returns(ret_1m=11.0, ret_3m=13.0, ret_6m=15.0, ret_1y=18.0, ret_3y=25.0)
        cat = _full_returns(ret_1m=1.0, ret_3m=3.0, ret_6m=5.0, ret_1y=8.0, ret_3y=15.0)
        assert score_peer_performance(fund, cat) == 70

    def test_minus_10pp_weighted_excess_scores_30(self):
        """-10pp excess in every period → weighted_excess=-10 → 50 - 10*2 = 30."""
        fund = _full_returns(ret_1m=-9.0, ret_3m=-7.0, ret_6m=-5.0, ret_1y=-2.0, ret_3y=5.0)
        cat = _full_returns(ret_1m=1.0, ret_3m=3.0, ret_6m=5.0, ret_1y=8.0, ret_3y=15.0)
        assert score_peer_performance(fund, cat) == 30

    def test_extreme_positive_excess_clamps_to_100(self):
        """+100pp excess everywhere → 50 + 100*2 = 250 → clamped to 100."""
        fund = _full_returns(ret_1m=101.0, ret_3m=103.0, ret_6m=105.0, ret_1y=108.0, ret_3y=115.0)
        cat = _full_returns(ret_1m=1.0, ret_3m=3.0, ret_6m=5.0, ret_1y=8.0, ret_3y=15.0)
        assert score_peer_performance(fund, cat) == 100

    def test_extreme_negative_excess_clamps_to_0(self):
        """-100pp excess everywhere → 50 - 100*2 = -150 → clamped to 0."""
        fund = _full_returns(ret_1m=-99.0, ret_3m=-97.0, ret_6m=-95.0, ret_1y=-92.0, ret_3y=-85.0)
        cat = _full_returns(ret_1m=1.0, ret_3m=3.0, ret_6m=5.0, ret_1y=8.0, ret_3y=15.0)
        assert score_peer_performance(fund, cat) == 0

    def test_missing_period_in_fund_treated_as_zero_excess(self):
        """Fund dict missing ret_1m → excess for that period is 0 (no contribution).

        Only ret_1y differs by +10pp → weighted_excess = 10 * 0.35 = 3.5 → 57.
        """
        fund = {"ret_3m": 3.0, "ret_6m": 5.0, "ret_1y": 18.0, "ret_3y": 15.0}  # no ret_1m
        cat = _full_returns(ret_1m=1.0, ret_3m=3.0, ret_6m=5.0, ret_1y=8.0, ret_3y=15.0)
        # weighted_excess = 0.35 * 10 = 3.5 → 50 + 3.5*2 = 57
        assert score_peer_performance(fund, cat) == 57

    def test_custom_period_weights_used(self):
        """Passing custom weights changes the score.

        Custom weights: only ret_1y matters (weight 1.0).
        Fund +10pp on ret_1y only → weighted_excess = 10 → 70.
        """
        fund = _full_returns(ret_1m=0.0, ret_3m=0.0, ret_6m=0.0, ret_1y=10.0, ret_3y=0.0)
        cat = _full_returns(ret_1m=0.0, ret_3m=0.0, ret_6m=0.0, ret_1y=0.0, ret_3y=0.0)
        custom_weights = {"ret_1m": 0.0, "ret_3m": 0.0, "ret_6m": 0.0, "ret_1y": 1.0, "ret_3y": 0.0}
        assert score_peer_performance(fund, cat, period_weights=custom_weights) == 70


class TestPeriodWeights:
    def test_default_weights_sum_to_one(self):
        """Default PERIOD_WEIGHTS must sum to exactly 1.0."""
        assert sum(PERIOD_WEIGHTS.values()) == pytest.approx(1.0)

    def test_default_weights_has_all_five_periods(self):
        """Default PERIOD_WEIGHTS covers the 5 standard periods."""
        expected = {"ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_3y"}
        assert set(PERIOD_WEIGHTS.keys()) == expected

    def test_default_weights_match_spec(self):
        """Spec-defined weights: 0.10/0.15/0.20/0.35/0.20."""
        assert PERIOD_WEIGHTS == {
            "ret_1m": 0.10,
            "ret_3m": 0.15,
            "ret_6m": 0.20,
            "ret_1y": 0.35,
            "ret_3y": 0.20,
        }


class TestEmptyInputGuard:
    def test_empty_fund_returns_raises(self):
        """No periods in fund_returns → InsufficientDataError, not fabricated 50.

        Finance principle: never fabricate a neutral score for missing data.
        """
        with pytest.raises(InsufficientDataError, match="无收益率数据"):
            score_peer_performance({}, _full_returns())

    def test_no_matching_periods_raises(self):
        """fund_returns has periods not in period_weights → no match → raise."""
        fund = {"ret_10y": 5.0}  # not a recognized period
        cat = _full_returns()
        with pytest.raises(InsufficientDataError):
            score_peer_performance(fund, cat)
