"""Tests for discover_funds MCP tool — two-stage discovery pipeline."""
import pytest
from unittest.mock import patch, MagicMock
from src.tools.discover import discover_funds, _STAGE2_CANDIDATES


class TestDiscoverFunds:
    def test_returns_top_n_results_sorted_by_score(self, monkeypatch):
        """End-to-end: mock pool + nav_store, verify top_n sorted output."""
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index",
                            _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages",
                            lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store",
                            _mock_nav_store)
        result = discover_funds(risk_level="conservative", top_n=3)
        assert result["count"] <= 3
        scores = [r["score"] for r in result["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_allowed_types_filter(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        result = discover_funds(risk_level="conservative", allowed_types="bond", top_n=5)
        for r in result["results"]:
            assert r["type"] == "bond"

    def test_empty_pool_returns_count_zero(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", lambda: {})
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        result = discover_funds(risk_level="conservative")
        assert result["count"] == 0
        assert result["results"] == []

    def test_empty_navstore_returns_error(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        empty_nav = MagicMock()
        empty_nav.coverage_report.return_value = {"fund_count": 0}
        monkeypatch.setattr("src.tools.discover._get_nav_store", lambda: empty_nav)
        result = discover_funds(risk_level="conservative")
        assert "error" in result
        assert "backfill" in result["error"]

    def test_diagnostic_fields_populated(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        result = discover_funds(risk_level="conservative", top_n=3)
        assert "stage1_evaluated" in result
        assert "stage2_evaluated" in result
        assert result["stage1_evaluated"] > 0

    def test_invalid_risk_level_raises(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        with pytest.raises(ValueError):
            discover_funds(risk_level="invalid")


# ── Test fixtures ──────────────────────────────────────────────────
from decimal import Decimal
from src.data.sources.fund_pool import PoolFund


def _pf(code, fund_type="bond", morningstar=4, ret_1y=5.0):
    return PoolFund(
        code=code, name=f"Fund {code}", fund_type=fund_type,
        raw_type=fund_type, manager="M", fee=Decimal("0.015"),
        ret_1m=0.5, ret_3m=1.5, ret_6m=3.0, ret_1y=ret_1y, ret_3y=15.0,
        rating_morningstar=morningstar, rating_shanghai=morningstar,
        rating_zhaoshang=morningstar, rating_jiAn=morningstar,
    )


def _mock_pool_index():
    return {f"{i:06d}": _pf(f"{i:06d}", ret_1y=5.0 + i) for i in range(20)}


_MOCK_AVGS = {
    "bond": {"ret_1m": 0.19, "ret_3m": 1.41, "ret_6m": 2.04, "ret_1y": 4.19, "ret_3y": 11.18},
    "mixed": {"ret_1m": 2.0, "ret_3m": 13.0, "ret_6m": 13.0, "ret_1y": 39.0, "ret_3y": 38.0},
}


def _mock_nav_store():
    store = MagicMock()
    store.coverage_report.return_value = {"fund_count": 20}
    store.get_nav_series.return_value = [1.0 + i * 0.001 for i in range(252)]
    return store
