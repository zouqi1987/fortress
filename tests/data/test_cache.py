"""Tests for src/data/cache.py — TTL-based SQLite cache."""
import time

import pytest

from src.data.cache import MarketCache


class TestMarketCache:
    def test_get_missing_key_returns_none(self, tmp_path):
        cache = MarketCache(str(tmp_path / "test.db"))
        assert cache.get("nonexistent") is None

    def test_set_and_get(self, tmp_path):
        cache = MarketCache(str(tmp_path / "test.db"))
        cache.set("key1", '{"value": 42}', ttl_seconds=3600)
        assert cache.get("key1") == '{"value": 42}'

    def test_expired_returns_none(self, tmp_path):
        cache = MarketCache(str(tmp_path / "test.db"))
        cache.set("key1", '{"value": 42}', ttl_seconds=0)
        time.sleep(0.01)  # ensure time has passed
        assert cache.get("key1") is None

    def test_overwrite_updates_data_and_ttl(self, tmp_path):
        cache = MarketCache(str(tmp_path / "test.db"))
        cache.set("key1", '{"v": 1}', ttl_seconds=3600)
        cache.set("key1", '{"v": 2}', ttl_seconds=3600)
        assert cache.get("key1") == '{"v": 2}'

    def test_invalidate_deletes_matching(self, tmp_path):
        cache = MarketCache(str(tmp_path / "test.db"))
        cache.set("fund_nav:000001:2025-01-01:2025-06-19", "[1]", ttl_seconds=3600)
        cache.set("fund_nav:000002:2025-01-01:2025-06-19", "[2]", ttl_seconds=3600)
        cache.set("fund_info:000001", '{"name":"test"}', ttl_seconds=3600)

        deleted = cache.invalidate("fund_nav:%")
        assert deleted == 2
        assert cache.get("fund_nav:000001:2025-01-01:2025-06-19") is None
        assert cache.get("fund_nav:000002:2025-01-01:2025-06-19") is None
        assert cache.get("fund_info:000001") == '{"name":"test"}'

    def test_invalidate_no_match_returns_zero(self, tmp_path):
        cache = MarketCache(str(tmp_path / "test.db"))
        cache.set("key1", "data", ttl_seconds=3600)
        assert cache.invalidate("nonexistent%") == 0
        assert cache.get("key1") == "data"

    def test_close_connection(self, tmp_path):
        cache = MarketCache(str(tmp_path / "test.db"))
        cache.set("k", "v", ttl_seconds=60)
        cache.close()
        # After close, operations should fail
        with pytest.raises(Exception):
            cache.get("k")
