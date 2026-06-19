"""Tests for src/data/market.py — Protocol, dataclasses, and facade failover logic."""
from datetime import date
from decimal import Decimal

import pytest

from src.datatypes import FundInfo, IndexPoint, NAVPoint
from src.data.market import (
    CachedSource,
    MarketDataFacade,
    MarketDataSource,
)


class FakeSource(MarketDataSource):
    """Mock source for testing failover logic."""

    def __init__(self, name: str, *, succeed: bool = True, data: list[NAVPoint] | None = None):
        self._name = name
        self._succeed = succeed
        self._data = data or [
            NAVPoint(date=date(2025, 6, 19), nav=Decimal("1.5000"), acc_nav=Decimal("2.0000"))
        ]

    @property
    def name(self) -> str:
        return self._name

    def fetch_fund_nav(self, code: str, start: date, end: date) -> list[NAVPoint]:
        if not self._succeed:
            raise RuntimeError(f"{self._name}: simulated failure")
        return self._data

    def fetch_fund_info(self, code: str) -> FundInfo:
        if not self._succeed:
            raise RuntimeError(f"{self._name}: simulated failure")
        return FundInfo(
            code=code,
            name="Test Fund",
            type="mixed",
            net_asset_value=Decimal("500_000_000"),
            fee_rate=Decimal("0.015"),
            inception_date=date(2020, 1, 1),
        )

    def fetch_index_daily(self, code: str, start: date, end: date) -> list[IndexPoint]:
        if not self._succeed:
            raise RuntimeError(f"{self._name}: simulated failure")
        return [IndexPoint(date=date(2025, 6, 19), close=Decimal("3500.00"), volume=Decimal("1000000"))]


class TestMarketDataFacade:
    """Test the failover chain: try sources in order, skip failures."""

    def test_first_source_succeeds_returns_immediately(self):
        s1 = FakeSource("primary", succeed=True)
        s2 = FakeSource("backup", succeed=True)
        facade = MarketDataFacade([s1, s2])
        result = facade.fetch_fund_nav("000001", date(2025, 1, 1), date(2025, 6, 19))
        assert len(result) == 1
        assert result[0].nav == Decimal("1.5000")

    def test_first_fails_second_succeeds(self):
        s1 = FakeSource("primary", succeed=False)
        s2 = FakeSource("backup", succeed=True)
        facade = MarketDataFacade([s1, s2])
        result = facade.fetch_fund_nav("000001", date(2025, 1, 1), date(2025, 6, 19))
        assert len(result) == 1

    def test_all_sources_fail_raises(self):
        s1 = FakeSource("primary", succeed=False)
        s2 = FakeSource("backup", succeed=False)
        facade = MarketDataFacade([s1, s2])
        with pytest.raises(RuntimeError, match="All 2 sources failed"):
            facade.fetch_fund_nav("000001", date(2025, 1, 1), date(2025, 6, 19))

    def test_fund_info_failover(self):
        s1 = FakeSource("primary", succeed=False)
        s2 = FakeSource("backup", succeed=True)
        facade = MarketDataFacade([s1, s2])
        info = facade.fetch_fund_info("000001")
        assert info.code == "000001"
        assert info.type == "mixed"

    def test_index_daily_failover(self):
        s1 = FakeSource("primary", succeed=False)
        s2 = FakeSource("backup", succeed=True)
        facade = MarketDataFacade([s1, s2])
        result = facade.fetch_index_daily("000300", date(2025, 1, 1), date(2025, 6, 19))
        assert len(result) == 1
        assert result[0].close == Decimal("3500.00")


class TestCachedSource:
    """CachedSource: returns cached data when valid, raises on miss."""

    def test_cache_hit_returns_data(self, tmp_path):
        from src.data.cache import MarketCache

        cache = MarketCache(str(tmp_path / "cache.db"))
        cache.set(
            "fund_info:000001",
            '{"code":"000001","name":"test","type":"mixed",'
            '"net_asset_value":"500000000","fee_rate":"0.015","inception_date":"2020-01-01"}',
            ttl_seconds=3600,
        )

        source = CachedSource(cache)
        result = source.fetch_fund_info("000001")
        assert result.code == "000001"
        assert result.name == "test"

    def test_cache_miss_raises(self, tmp_path):
        from src.data.cache import MarketCache

        cache = MarketCache(str(tmp_path / "cache.db"))
        source = CachedSource(cache)
        with pytest.raises(RuntimeError, match="Cache miss"):
            source.fetch_fund_info("999999")

    def test_cache_expired_raises(self, tmp_path):
        from src.data.cache import MarketCache

        cache = MarketCache(str(tmp_path / "cache.db"))
        cache.set(
            "fund_info:000001",
            '{"code":"000001","name":"test","type":"mixed",'
            '"net_asset_value":"500000000","fee_rate":"0.015","inception_date":"2020-01-01"}',
            ttl_seconds=0,
        )

        source = CachedSource(cache)
        with pytest.raises(RuntimeError, match="Cache miss"):
            source.fetch_fund_info("000001")


class TestFullFallbackChain:
    """Integration: AKShare(❌) → Tiantian(❌) → Cache(✅)"""

    def test_fallback_to_cache_when_live_sources_fail(self, tmp_path):
        from src.data.cache import MarketCache

        cache = MarketCache(str(tmp_path / "cache.db"))
        cache.set(
            "fund_info:000001",
            '{"code":"000001","name":"Cached Fund","type":"bond",'
            '"net_asset_value":"100000000","fee_rate":"0.010","inception_date":"2018-01-01"}',
            ttl_seconds=3600,
        )

        primary = FakeSource("primary", succeed=False)
        backup = FakeSource("backup", succeed=False)
        cached = CachedSource(cache)

        facade = MarketDataFacade([primary, backup, cached])
        info = facade.fetch_fund_info("000001")
        assert info.code == "000001"
        assert info.name == "Cached Fund"
        assert info.type == "bond"

    def test_stops_at_first_success(self, tmp_path):
        """Primary succeeds → never tries backup or cache."""
        from src.data.cache import MarketCache

        cache = MarketCache(str(tmp_path / "cache.db"))
        cache.set(
            "fund_info:000001",
            '{"code":"000001","name":"cached","type":"mixed",'
            '"net_asset_value":"1","fee_rate":"0.01","inception_date":"2020-01-01"}',
            ttl_seconds=3600,
        )

        primary = FakeSource("primary", succeed=True)
        backup_called = [False]

        class SpyBackup(FakeSource):
            def fetch_fund_info(self, code):
                backup_called[0] = True
                return super().fetch_fund_info(code)

        backup = SpyBackup("backup", succeed=True)
        cached = CachedSource(cache)

        facade = MarketDataFacade([primary, backup, cached])
        info = facade.fetch_fund_info("000001")
        assert info.name == "Test Fund"  # from primary, not cache
        assert not backup_called[0]  # never reached backup
