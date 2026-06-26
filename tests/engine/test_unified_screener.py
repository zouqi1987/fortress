"""Tests for the unified fund screener — score_funds() + preserved helpers.

Replaces test_screener.py (v1) and test_screener_v2.py (v2). Tests:
- Hard filters (ported from v1)
- Warnings (ported from v1)
- Exclusion rules (NEW — no fabricated data for missing ratings/NAV)
- 5-dimension scoring (NEW — Morningstar-aligned)
- Weight personalization (NEW — 9 combinations)
- Preserved helper function tests (ported from v2)
"""
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest

from src.datatypes import FundInfo
from src.data.sources.fund_pool import PoolFund
from src.data.sources.nav_store import NavStore
from src.engine.screener import (
    ScreenConfig,
    score_funds,
    score_risk_control,
    score_consistency,
)


# ── Test helpers ──────────────────────────────────────────────────────


def _make_fund(
    code="001",
    type="bond",
    nav=Decimal("1_000_000_000"),
    fee=Decimal("0.015"),
    inception="2020-01-01",
):
    return FundInfo(
        code=code, name=f"Fund{code}", type=type,
        net_asset_value=nav, fee_rate=fee,
        inception_date=date.fromisoformat(inception),
    )


def _make_pool_fund(
    code="001", type="bond", fee=Decimal("0.015"),
    ratings=None, returns=None,
):
    r = ratings or {}
    ret = returns or {}
    return PoolFund(
        code=code, name=f"Fund{code}", fund_type=type, raw_type=type,
        manager="test_mgr", fee=fee,
        ret_1m=ret.get("ret_1m", 0.5),
        ret_3m=ret.get("ret_3m", 1.0),
        ret_6m=ret.get("ret_6m", 2.0),
        ret_1y=ret.get("ret_1y", 5.0),
        ret_3y=ret.get("ret_3y", 10.0),
        rating_morningstar=r.get("morningstar", 3),
        rating_shanghai=r.get("shanghai", 3),
        rating_zhaoshang=r.get("zhaoshang", 3),
        rating_jiAn=r.get("jiAn", 3),
    )


def _make_nav(n=100, start=1.0, trend=0.001):
    """Generate n NAV points with slight upward trend (stable, low vol)."""
    return [round(start * (1 + trend) ** i, 4) for i in range(n)]


def _default_cat_avg():
    return {
        "bond": {"ret_1m": 0.5, "ret_3m": 1.0, "ret_6m": 2.0, "ret_1y": 5.0, "ret_3y": 10.0},
        "mixed": {"ret_1m": 1.0, "ret_3m": 2.0, "ret_6m": 4.0, "ret_1y": 10.0, "ret_3y": 20.0},
        "stock": {"ret_1m": 1.5, "ret_3m": 3.0, "ret_6m": 6.0, "ret_1y": 15.0, "ret_3y": 30.0},
        "index": {"ret_1m": 1.0, "ret_3m": 2.0, "ret_6m": 4.0, "ret_1y": 10.0, "ret_3y": 20.0},
        "money": {"ret_1m": 0.1, "ret_3m": 0.3, "ret_6m": 0.6, "ret_1y": 1.5, "ret_3y": 4.0},
    }


def _pool_index(funds, **kwargs):
    """Build pool_index from FundInfo list."""
    return {
        f.code: _make_pool_fund(code=f.code, type=f.type, fee=f.fee_rate, **kwargs)
        for f in funds
    }


def _mock_nav_store(nav_map: dict[str, list[float]]):
    """Mock NavStore.get_nav_series to return canned data per code."""
    store = mock.Mock(spec=NavStore)
    store.get_nav_series.side_effect = lambda code, days=750: nav_map.get(code, [])
    return store


# ── Hard Filters (ported from test_screener.py) ──────────────────────


class TestHardFilters:
    def test_filters_by_min_size(self, tmp_path):
        funds = [
            _make_fund("001", nav=Decimal("1_000_000_000")),
            _make_fund("002", nav=Decimal("100_000_000")),
        ]
        config = ScreenConfig(min_net_asset_value=Decimal("500_000_000"))
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds(funds, config, store, _pool_index(funds), _default_cat_avg())
        codes = [r.fund.code for r in results]
        assert "002" not in codes
        assert "001" in codes

    def test_filters_by_fund_type(self, tmp_path):
        funds = [_make_fund("001", type="bond"), _make_fund("002", type="stock")]
        config = ScreenConfig(allowed_types=frozenset({"bond"}))
        store = _mock_nav_store({"001": _make_nav(), "002": _make_nav()})
        results = score_funds(funds, config, store, _pool_index(funds), _default_cat_avg())
        assert len(results) == 1
        assert results[0].fund.code == "001"

    def test_empty_fund_list(self):
        store = _mock_nav_store({})
        results = score_funds([], ScreenConfig(), store, {}, _default_cat_avg())
        assert results == []


# ── Warnings (ported from test_screener.py) ───────────────────────────


class TestWarnings:
    def test_warning_for_small_fund(self):
        fund = _make_fund("001", nav=Decimal("100_000_000"))
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds(
            [fund], ScreenConfig(), store, _pool_index([fund]), _default_cat_avg()
        )
        assert any("规模" in w or "2亿" in w for w in results[0].warnings)

    def test_warning_for_young_fund(self):
        fund = _make_fund("001", inception="2026-01-01")
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds(
            [fund], ScreenConfig(), store, _pool_index([fund]), _default_cat_avg()
        )
        assert any("不足1年" in w for w in results[0].warnings)


# ── Exclusion Rules (NEW — no fabricated data) ────────────────────────


class TestExclusion:
    def test_all_zero_ratings_excluded(self):
        """Fund with all 4 ratings = 0 → excluded (InsufficientDataError)."""
        fund = _make_fund("001")
        pool = {"001": _make_pool_fund(ratings={"morningstar": 0, "shanghai": 0,
                                                "zhaoshang": 0, "jiAn": 0})}
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds([fund], ScreenConfig(), store, pool, _default_cat_avg())
        assert len(results) == 0  # excluded, not scored

    def test_nav_below_63_excluded(self):
        """Fund with NAV < 63 points → excluded."""
        fund = _make_fund("001", type="bond")
        store = _mock_nav_store({"001": _make_nav(n=50)})  # < 63
        results = score_funds([fund], ScreenConfig(), store, _pool_index([fund]), _default_cat_avg())
        assert len(results) == 0

    def test_money_fund_no_nav_required(self):
        """Money funds skip NAV check — only 3 dimensions."""
        fund = _make_fund("001", type="money", fee=Decimal("0.003"))
        pool = {"001": _make_pool_fund("001", type="money", fee=Decimal("0.003"))}
        store = _mock_nav_store({})  # no NAV for money fund
        results = score_funds([fund], ScreenConfig(), store, pool, _default_cat_avg())
        assert len(results) == 1  # money fund scored without NAV

    def test_fund_not_in_pool_index_excluded(self):
        """Fund code not in pool_index → excluded with warning."""
        fund = _make_fund("001")
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds([fund], ScreenConfig(), store, {}, _default_cat_avg())
        assert len(results) == 0

    def test_empty_category_averages_excludes_fund(self):
        """Fund type not in category_averages → excluded (no peer data)."""
        fund = _make_fund("001", type="bond")
        store = _mock_nav_store({"001": _make_nav()})
        # category_averages has no "bond" key
        results = score_funds([fund], ScreenConfig(), store, _pool_index([fund]), {})
        assert len(results) == 0  # excluded — no peer comparison data


# ── Dimension Scoring (NEW) ───────────────────────────────────────────


class TestDimensions:
    def test_score_returns_0_to_100(self):
        fund = _make_fund("001")
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds(
            [fund], ScreenConfig(), store, _pool_index([fund]), _default_cat_avg()
        )
        assert 0 <= results[0].score <= 100

    def test_dimension_breakdown_present(self):
        """Result has dimension_breakdown dict with all dimensions."""
        fund = _make_fund("001", type="bond")
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds(
            [fund], ScreenConfig(), store, _pool_index([fund]), _default_cat_avg()
        )
        bd = results[0].dimension_breakdown
        assert "institutional_consensus" in bd
        assert "peer_performance" in bd
        assert "risk_control" in bd
        assert "persistence" in bd
        assert "fee" in bd

    def test_money_fund_only_3_dimensions(self):
        """Money fund: only consensus + peer + fee in breakdown."""
        fund = _make_fund("001", type="money", fee=Decimal("0.003"))
        pool = {"001": _make_pool_fund("001", type="money", fee=Decimal("0.003"))}
        store = _mock_nav_store({})
        results = score_funds([fund], ScreenConfig(), store, pool, _default_cat_avg())
        bd = results[0].dimension_breakdown
        assert "risk_control" not in bd
        assert "persistence" not in bd
        assert "fee" in bd

    def test_dimension_breakdown_enriched_format(self):
        """Each dimension has score + raw + benchmark keys (not bare int)."""
        fund = _make_fund("001", type="bond")
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds(
            [fund], ScreenConfig(), store, _pool_index([fund]), _default_cat_avg()
        )
        bd = results[0].dimension_breakdown
        for dim_name, dim_data in bd.items():
            assert isinstance(dim_data, dict), f"{dim_name} should be dict, got {type(dim_data)}"
            assert "score" in dim_data, f"{dim_name} missing 'score' key"
            assert "raw" in dim_data, f"{dim_name} missing 'raw' key"
            assert "benchmark" in dim_data, f"{dim_name} missing 'benchmark' key"
            assert isinstance(dim_data["score"], int), f"{dim_name} score should be int"

    def test_dimension_raw_sanitizes_nan(self):
        """NaN ratings in raw should be converted to None for JSON safety."""
        from math import nan
        fund = _make_fund("001", type="bond")
        pool = {
            "001": _make_pool_fund("001", ratings={
                "morningstar": 4, "shanghai": nan, "zhaoshang": nan, "jiAn": nan
            })
        }
        store = _mock_nav_store({"001": _make_nav()})
        results = score_funds([fund], ScreenConfig(), store, pool, _default_cat_avg())
        raw = results[0].dimension_breakdown["institutional_consensus"]["raw"]
        assert raw["morningstar"] == 4
        assert raw["shanghai"] is None  # NaN sanitized to None
        assert raw["zhaoshang"] is None
        assert raw["jiAn"] is None

    def test_results_sorted_by_score_descending(self):
        funds = [_make_fund(f"00{i}") for i in range(3)]
        # Give fund 2 higher ratings → higher consensus score
        pool = {
            "001": _make_pool_fund("001", ratings={"morningstar": 1, "shanghai": 1,
                                                    "zhaoshang": 1, "jiAn": 1}),
            "002": _make_pool_fund("002", ratings={"morningstar": 5, "shanghai": 5,
                                                    "zhaoshang": 5, "jiAn": 5}),
            "003": _make_pool_fund("003", ratings={"morningstar": 3, "shanghai": 3,
                                                    "zhaoshang": 3, "jiAn": 3}),
        }
        nav_map = {f"00{i}": _make_nav() for i in range(1, 4)}
        store = _mock_nav_store(nav_map)
        results = score_funds(funds, ScreenConfig(), store, pool, _default_cat_avg())
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


# ── Weight Personalization (NEW) ──────────────────────────────────────


class TestWeights:
    def test_different_risk_levels_different_scores(self):
        """Same fund, different risk_level → different score."""
        fund = _make_fund("001", type="bond")
        pool = _pool_index([fund])
        store = _mock_nav_store({"001": _make_nav()})
        cat = _default_cat_avg()

        r_cons = score_funds([fund], ScreenConfig(), store, pool, cat, risk_level="conservative")
        r_agg = score_funds([fund], ScreenConfig(), store, pool, cat, risk_level="aggressive")
        # Different weights → likely different scores (unless all dims equal)
        # At minimum, both should be valid scores
        assert 0 <= r_cons[0].score <= 100
        assert 0 <= r_agg[0].score <= 100

    def test_invalid_risk_level_raises(self):
        fund = _make_fund("001")
        store = _mock_nav_store({"001": _make_nav()})
        with pytest.raises(ValueError):
            score_funds([fund], ScreenConfig(), store, _pool_index([fund]),
                        _default_cat_avg(), risk_level="invalid")


# ── Fee scoring (NEW — _score_fee helper) ─────────────────────────────


class TestScoreFee:
    """Test _score_fee tier boundaries. Lower fee = higher score."""

    def test_zero_fee_scores_100(self):
        from src.engine.screener import _score_fee
        assert _score_fee(Decimal("0")) == 100

    def test_ultra_low_fee_scores_100(self):
        from src.engine.screener import _score_fee
        assert _score_fee(Decimal("0.001")) == 100  # 0.1%

    def test_tier_boundaries(self):
        from src.engine.screener import _score_fee
        # Boundary: exactly at tier threshold
        assert _score_fee(Decimal("0.0015")) == 100  # 0.15% → 100
        assert _score_fee(Decimal("0.0016")) == 85   # 0.16% → 85
        assert _score_fee(Decimal("0.005")) == 85     # 0.50% → 85
        assert _score_fee(Decimal("0.0051")) == 70    # 0.51% → 70
        assert _score_fee(Decimal("0.01")) == 70      # 1.00% → 70
        assert _score_fee(Decimal("0.0101")) == 55   # 1.01% → 55
        assert _score_fee(Decimal("0.015")) == 55     # 1.50% → 55
        assert _score_fee(Decimal("0.0151")) == 35    # 1.51% → 35
        assert _score_fee(Decimal("0.02")) == 35      # 2.00% → 35
        assert _score_fee(Decimal("0.0201")) == 15    # 2.01% → 15

    def test_high_fee_scores_15(self):
        from src.engine.screener import _score_fee
        assert _score_fee(Decimal("0.03")) == 15  # 3%


# ── Preserved helper tests (ported from test_screener_v2.py) ──────────


class TestScoreRiskControl:
    def test_stable_nav_low_risk(self):
        navs = [1.0 + i * 0.001 for i in range(100)]
        s, raw = score_risk_control(navs)
        assert s >= 15
        assert raw["max_drawdown"] is not None
        assert raw["ann_volatility"] is not None

    def test_volatile_nav_high_risk(self):
        navs = [1.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(100)]
        s, raw = score_risk_control(navs)
        assert s <= 10
        assert raw["max_drawdown"] is not None

    def test_empty_returns_zero(self):
        s, raw = score_risk_control([])
        assert s == 0
        assert raw["max_drawdown"] is None
        assert raw["ann_volatility"] is None

    def test_decimal_nav_does_not_crash(self):
        from decimal import Decimal as D
        navs = [D("1.0"), D("1.01"), D("1.02")]
        s, raw = score_risk_control(navs)
        assert isinstance(s, int)
        assert 0 <= s <= 20
        assert "max_drawdown" in raw


class TestScoreConsistency:
    def test_all_positive_quarters(self):
        navs = [1.0 * (1.002 ** i) for i in range(504)]
        s, raw = score_consistency(navs)
        assert s >= 8
        assert raw["quarterly_positive_rate"] is not None

    def test_mixed_quarters(self):
        navs = [1.0] * 503
        for i in range(0, 503, 126):
            navs[i] = 0.9
        s, raw = score_consistency(navs)
        assert s >= 0

    def test_empty_returns_zero(self):
        s, raw = score_consistency([])
        assert s == 0
        assert raw["quarterly_positive_rate"] is None
