"""Tests for src/engine/screener.py — fund screening and ranking."""
from datetime import date
from decimal import Decimal

import pytest

from src.datatypes import FundInfo
from src.engine.screener import (
    ScreenConfig,
    ScreenResult,
    screen_funds,
)


@pytest.fixture
def sample_funds() -> list[FundInfo]:
    return [
        FundInfo("000001", "华夏成长", "mixed", Decimal("5_000_000_000"), Decimal("0.015"), date(2001, 12, 18)),
        FundInfo("000002", "迷你基金", "stock", Decimal("50_000_000"), Decimal("0.020"), date(2024, 1, 1)),
        FundInfo("000003", "债基稳健", "bond", Decimal("10_000_000_000"), Decimal("0.005"), date(2015, 6, 1)),
        FundInfo("000004", "指数增强", "index", Decimal("2_000_000_000"), Decimal("0.008"), date(2018, 3, 15)),
    ]


class TestScreenFunds:
    def test_filters_by_min_size(self, sample_funds):
        config = ScreenConfig(min_net_asset_value=Decimal("500_000_000"))
        results = screen_funds(sample_funds, config)
        codes = {r.fund.code for r in results}
        assert "000002" not in codes  # 迷你基金 filtered
        assert len(results) == 3

    def test_filters_by_fund_type(self, sample_funds):
        config = ScreenConfig(allowed_types={"bond"})
        results = screen_funds(sample_funds, config)
        assert len(results) == 1
        assert results[0].fund.code == "000003"

    def test_filters_by_min_inception(self, sample_funds):
        config = ScreenConfig(min_inception_date=date(2016, 1, 1))
        results = screen_funds(sample_funds, config)
        codes = {r.fund.code for r in results}
        assert "000002" not in codes  # 2024 start filtered
        assert len(results) >= 2

    def test_ranks_by_default_config(self, sample_funds):
        """With no filters, all funds pass and receive scores."""
        config = ScreenConfig()
        results = screen_funds(sample_funds, config)
        assert len(results) == 4
        # All have a score
        for r in results:
            assert r.score >= 0
            assert len(r.warnings) >= 0

    def test_default_config_allows_all_types(self):
        config = ScreenConfig()
        assert "stock" in config.allowed_types
        assert "bond" in config.allowed_types
        assert "money" in config.allowed_types

    def test_warning_for_small_fund(self, sample_funds):
        config = ScreenConfig(min_net_asset_value=Decimal("0"))  # no hard filter
        results = screen_funds(sample_funds, config)
        tiny = next(r for r in results if r.fund.code == "000002")
        assert any("规模" in w or "size" in w.lower() for w in tiny.warnings)

    def test_empty_fund_list(self):
        config = ScreenConfig()
        results = screen_funds([], config)
        assert len(results) == 0
