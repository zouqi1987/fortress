"""MCP tools: market data lookup — fund info, NAV history, and index data.

Cache transparency: every response includes data_source field.
When data comes from cache (not live API), stale_warning is added
with the cache timestamp so LLM can disclose this to the user.
"""
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from src.data.cache import MarketCache
from src.data.market import CachedSource, MarketDataFacade
from src.data.sources.akshare import AKShareSource
from src.data.sources.eastmoney import EastmoneySource
from src.data.sources.tiantian import TiantianSource

_CACHE_DIR = os.environ.get("FORTRESS_DATA_DIR", "data")

# Timezone-aware local timezone for cache timestamp display
_LOCAL_TZ = datetime.now(timezone.utc).astimezone().tzinfo


def _cache_awareness(facade: MarketDataFacade, cache: MarketCache, code: str) -> dict:
    """Build data_source metadata dict. Adds stale_warning if from cache.

    Returns dict with data_source and optionally cached_at, stale_warning.
    """
    source = facade.last_source or "unknown"
    meta: dict = {"data_source": source}

    if source == "cache":
        # Try to find the cache timestamp for this code
        ts = (
            cache.get_timestamp(f"fund_info:{code}")
            or cache.get_timestamp(f"index_daily:{code}")
        )
        if ts is not None:
            cached_dt = datetime.fromtimestamp(ts, tz=_LOCAL_TZ)
            cached_str = cached_dt.strftime("%Y-%m-%d %H:%M:%S")
            meta["cached_at"] = cached_str
            meta["stale_warning"] = (
                f"⚠️ 当前数据来自本地缓存（缓存时间: {cached_str}），"
                f"非实时接口数据。建议稍后重试获取最新数据。"
            )
        else:
            meta["stale_warning"] = (
                "⚠️ 当前数据来自本地缓存，非实时接口数据。建议稍后重试获取最新数据。"
            )

    return meta


def _build_facade():
    """Build the standard three-level data facade."""
    cache = MarketCache(f"{_CACHE_DIR}/market_cache.db")
    cached = CachedSource(cache)
    return MarketDataFacade([AKShareSource(), TiantianSource(), cached]), cache


# ── Fund Lookup ────────────────────────────────────────────────────────


def lookup_fund(code: str, start: str = "", end: str = "") -> dict:
    """Look up fund information and recent NAV.

    Uses three-level fallback: akshare → tiantian → local cache.
    Results are cached for 24h on successful fetch.

    Args:
        code: fund code (e.g. "000001")
        start: Optional start date "YYYY-MM-DD" for NAV history (default: 30 days ago).
        end: Optional end date "YYYY-MM-DD" for NAV history (default: today).
    """
    try:
        facade, cache = _build_facade()

        today = date.today()
        end_date = date.fromisoformat(end) if end else today
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=30)

        info = facade.fetch_fund_info(code)
        navs = facade.fetch_fund_nav(code, start_date, end_date)

        _cache_results(cache, info, navs)

        cache_meta = _cache_awareness(facade, cache, code)

        result = {
            "code": info.code,
            "name": info.name,
            "type": info.type,
            "net_asset_value": float(info.net_asset_value),
            "fee_rate": float(info.fee_rate),
            "inception_date": info.inception_date.isoformat(),
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "recent_nav": [
                {"date": n.date.isoformat(), "nav": float(n.nav), "acc_nav": float(n.acc_nav)}
                for n in navs[-5:]  # last 5 days
            ],
            **cache_meta,
        }
        return result
    except Exception as e:
        return {"error": str(e), "code": code}


# ── Index Lookup ───────────────────────────────────────────────────────


def lookup_index(code: str, start: str = "", end: str = "") -> dict:
    """Look up index daily data (e.g. SH000001 for 上证指数).

    Uses three-level fallback: akshare → eastmoney → local cache.

    Args:
        code: Index code (e.g. "000001" for 上证指数, "399001" for 深证成指).
        start: Optional start date "YYYY-MM-DD" (default: 90 days ago).
        end: Optional end date "YYYY-MM-DD" (default: today).
    """
    try:
        facade, cache = _build_facade()

        today = date.today()
        end_date = date.fromisoformat(end) if end else today
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=90)

        data = facade.fetch_index_daily(code, start_date, end_date)

        # Cache for future fallback
        _cache_index_results(cache, code, data)

        cache_meta = _cache_awareness(facade, cache, code)

        result = {
            "code": code,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "count": len(data),
            "data": [
                {"date": d.date.isoformat(), "close": float(d.close), "volume": float(d.volume)}
                for d in data
            ],
            **cache_meta,
        }
        return result
    except Exception as e:
        return {"error": str(e), "code": code}


# ── Cache Helpers ───────────────────────────────────────────────────────


def _cache_results(cache: MarketCache, info, navs) -> None:
    """Write fetched results to cache for future fallback use."""
    try:
        cache.set(
            f"fund_info:{info.code}",
            json.dumps({
                "code": info.code, "name": info.name, "type": info.type,
                "net_asset_value": str(info.net_asset_value),
                "fee_rate": str(info.fee_rate),
                "inception_date": info.inception_date.isoformat(),
            }),
            ttl_seconds=86400,  # 24h
        )
        if navs:
            cache.set(
                f"fund_nav:{info.code}:{navs[0].date}:{navs[-1].date}",
                json.dumps([
                    {"date": n.date.isoformat(), "nav": str(n.nav), "acc_nav": str(n.acc_nav)}
                    for n in navs
                ]),
                ttl_seconds=86400,
            )
    except Exception:
        pass  # cache write failures are non-fatal


def _cache_index_results(cache: MarketCache, code: str, data) -> None:
    """Write index data to cache."""
    try:
        if data:
            cache.set(
                f"index_daily:{code}:{data[0].date}:{data[-1].date}",
                json.dumps([
                    {"date": d.date.isoformat(), "close": str(d.close), "volume": str(d.volume)}
                    for d in data
                ]),
                ttl_seconds=86400,
            )
    except Exception:
        pass
