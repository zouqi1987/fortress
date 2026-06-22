"""Tests for category peer benchmark — compute_category_averages()."""
from decimal import Decimal

import pytest

from src.data.sources.fund_pool import PoolFund
from src.engine.category_benchmark import compute_category_averages


def _make_pool_fund(code, name, fund_type="bond", **returns):
    """Helper: create a PoolFund with given return values, defaults to 0."""
    return PoolFund(
        code=code, name=name, fund_type=fund_type, manager="test",
        fee=Decimal("0.015"),
        ret_1m=returns.get("ret_1m", 0.0),
        ret_3m=returns.get("ret_3m", 0.0),
        ret_6m=returns.get("ret_6m", 0.0),
        ret_1y=returns.get("ret_1y", 0.0),
        ret_3y=returns.get("ret_3y", 0.0),
        rating_morningstar=0, rating_shanghai=0,
        rating_zhaoshang=0, rating_jiAn=0,
    )


class TestComputeCategoryAverages:
    def test_multi_fund_average(self):
        """3 bond funds (ret_1y=2,4,6) → avg=4.0."""
        funds = [
            _make_pool_fund("001", "债基A", ret_1y=2.0),
            _make_pool_fund("002", "债基B", ret_1y=4.0),
            _make_pool_fund("003", "债基C", ret_1y=6.0),
        ]
        result = compute_category_averages(funds)
        assert "bond" in result
        assert result["bond"]["ret_1y"] == pytest.approx(4.0)

    def test_empty_pool_returns_empty(self):
        assert compute_category_averages([]) == {}

    def test_multiple_categories(self):
        """Bond and mixed funds return separate averages."""
        funds = [
            _make_pool_fund("001", "债基A", "bond", ret_1y=5.0),
            _make_pool_fund("002", "混合A", "mixed", ret_1y=15.0),
            _make_pool_fund("003", "债基B", "bond", ret_1y=3.0),
        ]
        result = compute_category_averages(funds)
        assert result["bond"]["ret_1y"] == pytest.approx(4.0)
        assert result["mixed"]["ret_1y"] == pytest.approx(15.0)

    def test_all_periods_present(self):
        """Result has all 5 period keys for each category."""
        funds = [
            _make_pool_fund("001", "债基", ret_1m=0.1, ret_3m=0.5,
                           ret_6m=1.0, ret_1y=2.0, ret_3y=5.0),
        ]
        result = compute_category_averages(funds)
        periods = ["ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_3y"]
        for p in periods:
            assert p in result["bond"], f"Missing period: {p}"
        assert len(result["bond"]) == 5

    def test_unknown_type_still_computes(self):
        """Funds with unrecognized type get their own category."""
        funds = [
            _make_pool_fund("001", "另类", "other", ret_1y=8.0),
        ]
        result = compute_category_averages(funds)
        assert "other" in result
        assert result["other"]["ret_1y"] == pytest.approx(8.0)
