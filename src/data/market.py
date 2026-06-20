"""Market data protocol, DTOs, fallback facade, and cache-backed source.

Defines the MarketDataSource Protocol that all adapters implement,
plus the MarketDataFacade that chains them with failover.
"""
import json
import logging
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from src.datatypes import FundInfo, IndexPoint, NAVPoint

logger = logging.getLogger(__name__)


# ── Protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class MarketDataSource(Protocol):
    """All data source adapters implement this interface."""

    @property
    def name(self) -> str: ...

    def fetch_fund_nav(self, code: str, start: date, end: date) -> list[NAVPoint]: ...

    def fetch_fund_info(self, code: str) -> FundInfo: ...

    def fetch_index_daily(self, code: str, start: date, end: date) -> list[IndexPoint]: ...


# ── Facade ───────────────────────────────────────────────────────────


class MarketDataFacade:
    """Try sources in order. First success wins. Raises if all fail.

    Track last_source so callers can detect cache vs live data.
    """

    def __init__(self, sources: list[MarketDataSource]) -> None:
        if not sources:
            raise ValueError("At least one data source required")
        self._sources = sources
        self._last_source: str = ""
        self._last_method: str = ""

    @property
    def last_source(self) -> str:
        """Name of the source that succeeded in the most recent call."""
        return self._last_source

    def fetch_fund_nav(self, code: str, start: date, end: date) -> list[NAVPoint]:
        return self._try_all("fetch_fund_nav", code, start, end)

    def fetch_fund_info(self, code: str) -> FundInfo:
        return self._try_all("fetch_fund_info", code)

    def fetch_index_daily(self, code: str, start: date, end: date) -> list[IndexPoint]:
        return self._try_all("fetch_index_daily", code, start, end)

    def _try_all(self, method: str, *args):
        """Try each source; on success return result. On failure, log and try next."""
        errors: list[str] = []
        self._last_source = ""
        self._last_method = method
        for source in self._sources:
            try:
                fn = getattr(source, method)
                result = fn(*args)
                self._last_source = source.name
                return result
            except Exception as e:
                msg = f"[{source.name}] {method} failed: {e}"
                logger.warning(msg)
                errors.append(msg)
        raise RuntimeError(
            f"All {len(self._sources)} sources failed for {method}: {'; '.join(errors)}"
        )


# ── Cache-backed Source ──────────────────────────────────────────────


class CachedSource:
    """MarketDataSource that reads from local cache. Raises on miss.

    Always placed last in the source chain — serves as the final fallback
    before giving up entirely.
    """

    name = "cache"

    def __init__(self, cache):
        # Lazy import to avoid circular dependency at module level
        from src.data.cache import MarketCache

        self._cache: MarketCache = cache

    def fetch_fund_nav(self, code: str, start: date, end: date) -> list[NAVPoint]:
        key = f"fund_nav:{code}:{start}:{end}"
        raw = self._cache.get(key)
        if raw is None:
            raise RuntimeError(f"Cache miss for {key}")
        data = json.loads(raw)
        return [
            NAVPoint(
                date=date.fromisoformat(d["date"]),
                nav=Decimal(d["nav"]),
                acc_nav=Decimal(d["acc_nav"]),
            )
            for d in data
        ]

    def fetch_fund_info(self, code: str) -> FundInfo:
        key = f"fund_info:{code}"
        raw = self._cache.get(key)
        if raw is None:
            raise RuntimeError(f"Cache miss for {key}")
        d = json.loads(raw)
        return FundInfo(
            code=d["code"],
            name=d["name"],
            type=d["type"],
            net_asset_value=Decimal(d["net_asset_value"]),
            fee_rate=Decimal(d["fee_rate"]),
            inception_date=date.fromisoformat(d["inception_date"]),
        )

    def fetch_index_daily(self, code: str, start: date, end: date) -> list[IndexPoint]:
        key = f"index_daily:{code}:{start}:{end}"
        raw = self._cache.get(key)
        if raw is None:
            raise RuntimeError(f"Cache miss for {key}")
        data = json.loads(raw)
        return [
            IndexPoint(
                date=date.fromisoformat(d["date"]),
                close=Decimal(d["close"]),
                volume=Decimal(d["volume"]),
            )
            for d in data
        ]
