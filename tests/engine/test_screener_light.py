"""Tests for score_funds_light — Stage 1 scoring (3 dims, no NavStore)."""
import pytest
from decimal import Decimal
from src.engine.screener import score_funds_light, LightResult, ScreenConfig
from src.data.sources.fund_pool import PoolFund


def _make_pool_fund(
    code="000001", name="Test Fund", fund_type="bond", raw_type="债券型-纯债",
    manager="张三", fee=Decimal("0.015"),
    ret_1y=5.0, ret_3y=15.0, ret_1m=0.5, ret_3m=1.5, ret_6m=3.0,
    morningstar=4, shanghai=4, zhaoshang=4, jiAn=4,
):
    return PoolFund(
        code=code, name=name, fund_type=fund_type, raw_type=raw_type,
        manager=manager, fee=fee,
        ret_1m=ret_1m, ret_3m=ret_3m, ret_6m=ret_6m, ret_1y=ret_1y, ret_3y=ret_3y,
        rating_morningstar=morningstar, rating_shanghai=shanghai,
        rating_zhaoshang=zhaoshang, rating_jiAn=jiAn,
    )


CATEGORY_AVERAGES = {
    "bond": {"ret_1m": 0.19, "ret_3m": 1.41, "ret_6m": 2.04, "ret_1y": 4.19, "ret_3y": 11.18},
}


class TestScoreFundsLight:
    def test_scores_single_fund_returns_one_result(self):
        pool = [_make_pool_fund()]
        config = ScreenConfig()
        results = score_funds_light(pool, config, CATEGORY_AVERAGES, "conservative")
        assert len(results) == 1
        assert results[0].code == "000001"
        assert 0 <= results[0].score <= 100

    def test_excludes_fund_with_all_zero_ratings(self):
        pool = [_make_pool_fund(morningstar=0, shanghai=0, zhaoshang=0, jiAn=0)]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        assert len(results) == 0  # excluded — no ratings

    def test_excludes_fund_with_no_category_averages(self):
        pool = [_make_pool_fund(fund_type="exotic_type")]
        empty_avgs = {}
        results = score_funds_light(pool, ScreenConfig(), empty_avgs, "conservative")
        assert len(results) == 0

    def test_filters_by_allowed_types(self):
        pool = [_make_pool_fund(code="A", fund_type="bond"),
                _make_pool_fund(code="B", fund_type="mixed")]
        config = ScreenConfig(allowed_types=frozenset({"bond"}))
        results = score_funds_light(pool, config, CATEGORY_AVERAGES, "conservative")
        assert len(results) == 1
        assert results[0].code == "A"

    def test_filters_by_max_fee_rate(self):
        pool = [_make_pool_fund(code="A", fee=Decimal("0.010")),
                _make_pool_fund(code="B", fee=Decimal("0.020"))]
        config = ScreenConfig(max_fee_rate=Decimal("0.015"))
        results = score_funds_light(pool, config, CATEGORY_AVERAGES, "conservative")
        assert len(results) == 1
        assert results[0].code == "A"

    def test_higher_rated_fund_scores_higher(self):
        pool = [_make_pool_fund(code="low", morningstar=2, shanghai=2, zhaoshang=2, jiAn=2),
                _make_pool_fund(code="high", morningstar=5, shanghai=5, zhaoshang=5, jiAn=5)]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        assert results[0].code == "high"  # sorted desc
        assert results[0].score > results[1].score

    def test_results_sorted_by_score_descending(self):
        pool = [_make_pool_fund(code="low", morningstar=2, shanghai=2, zhaoshang=2, jiAn=2),
                _make_pool_fund(code="high", morningstar=5, shanghai=5, zhaoshang=5, jiAn=5),
                _make_pool_fund(code="mid", morningstar=3, shanghai=3, zhaoshang=3, jiAn=3)]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_dimension_breakdown_has_exactly_3_dims(self):
        pool = [_make_pool_fund()]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        dims = results[0].dimension_breakdown
        assert set(dims.keys()) == {"institutional_consensus", "peer_performance", "fee"}

    def test_money_fund_uses_money_weights(self):
        """Money funds: Stage 1 weights == full weights (3-dim already)."""
        pool = [_make_pool_fund(code="M", fund_type="money", raw_type="货币型")]
        avgs = {"money": {"ret_1m": 0.1, "ret_3m": 0.3, "ret_6m": 0.6, "ret_1y": 1.5, "ret_3y": 4.0}}
        results = score_funds_light(pool, ScreenConfig(), avgs, "conservative")
        assert len(results) == 1
        assert set(results[0].dimension_breakdown.keys()) == {"institutional_consensus", "peer_performance", "fee"}

    def test_invalid_risk_level_raises(self):
        pool = [_make_pool_fund()]
        with pytest.raises(ValueError):
            score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "wild")
