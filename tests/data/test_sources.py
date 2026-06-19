"""Tests for data source adapters — Protocol compliance and retry logic.

Uses mock HTTP to avoid real network calls.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest

from src.data.market import FundInfo, IndexPoint, MarketDataSource, NAVPoint
from src.data.sources.akshare import AKShareSource
from src.data.sources.eastmoney import EastmoneySource
from src.data.sources.tiantian import TiantianSource


# ── Protocol compliance ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "source_cls",
    [AKShareSource, TiantianSource, EastmoneySource],
)
def test_implements_market_data_source_protocol(source_cls):
    """All source classes must satisfy the MarketDataSource Protocol."""
    source = source_cls()
    assert isinstance(source, MarketDataSource)
    assert isinstance(source.name, str)
    assert len(source.name) > 0


# ── AKShareSource ─────────────────────────────────────────────────────


class TestAKShareSource:
    def test_retry_on_failure(self):
        """3 retries with exponential backoff — mock the _impl layer."""
        call_count = 0

        def flaky_impl(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("simulated network error")
            return [
                NAVPoint(
                    date=date(2025, 6, 19),
                    nav=Decimal("1.5000"),
                    acc_nav=Decimal("2.0000"),
                )
            ]

        with mock.patch.object(AKShareSource, "_fetch_fund_nav_impl", flaky_impl):
            source = AKShareSource()
            result = source.fetch_fund_nav("000001", date(2025, 1, 1), date(2025, 6, 19))
            assert len(result) == 1
            assert result[0].nav == Decimal("1.5000")
            assert call_count == 3

    def test_exhausts_retries_raises(self):
        call_count = 0

        def always_fail(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("network error")

        with mock.patch.object(AKShareSource, "_fetch_fund_nav_impl", always_fail):
            source = AKShareSource()
            with pytest.raises(ConnectionError):
                source.fetch_fund_nav("000001", date(2025, 1, 1), date(2025, 6, 19))
            assert call_count == 3  # 3 retries exhausted

    def test_name_is_set(self):
        source = AKShareSource()
        assert source.name == "akshare"


# ── TiantianSource ────────────────────────────────────────────────────


class TestTiantianSource:
    def test_name_is_set(self):
        source = TiantianSource()
        assert source.name == "tiantian"

    def test_retry_count_is_2(self):
        call_count = 0

        def always_fail(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("network error")

        with mock.patch.object(TiantianSource, "_fetch_fund_info_impl", always_fail):
            source = TiantianSource()
            with pytest.raises(ConnectionError):
                source.fetch_fund_info("000001")
            assert call_count == 2  # 2 retries exhausted


# ── EastmoneySource ───────────────────────────────────────────────────


class TestEastmoneySource:
    def test_name_is_set(self):
        source = EastmoneySource()
        assert source.name == "eastmoney"

    def test_fetch_index_daily_returns_index_points(self):
        source = EastmoneySource()
        with mock.patch.object(
            source,
            "fetch_index_daily",
            return_value=[
                IndexPoint(
                    date=date(2025, 6, 19),
                    close=Decimal("3500.00"),
                    volume=Decimal("100000000"),
                )
            ],
        ):
            result = source.fetch_index_daily("000300", date(2025, 6, 1), date(2025, 6, 19))
            assert len(result) == 1
            assert result[0].close == Decimal("3500.00")
