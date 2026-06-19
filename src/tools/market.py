"""MCP tool: market data lookup."""
import json
import os
from datetime import date, timedelta
from decimal import Decimal

from src.data.cache import MarketCache
from src.data.market import CachedSource, MarketDataFacade
from src.data.sources.akshare import AKShareSource
from src.data.sources.eastmoney import EastmoneySource
from src.data.sources.tiantian import TiantianSource

_CACHE_DIR = os.environ.get("FORTRESS_DATA_DIR", "data")


def lookup_fund(code: str) -> dict:
    """Look up fund information and recent NAV.

    Uses three-level fallback: akshare → tiantian → local cache.
    Results are cached for 24h on successful fetch.

    Args:
        code: fund code (e.g. "000001")

    Returns fund info dict or error message.
    """
    try:
        cache = MarketCache(f"{_CACHE_DIR}/market_cache.db")
        cached = CachedSource(cache)

        # Full ADR-5 fallback chain: akshare → tiantian → cache
        facade = MarketDataFacade([AKShareSource(), TiantianSource(), cached])

        end = date.today()
        start = end - timedelta(days=30)

        info = facade.fetch_fund_info(code)
        navs = facade.fetch_fund_nav(code, start, end)

        # Cache successful results for next time
        _cache_results(cache, info, navs)

        return {
            "code": info.code,
            "name": info.name,
            "type": info.type,
            "net_asset_value": float(info.net_asset_value),
            "fee_rate": float(info.fee_rate),
            "inception_date": info.inception_date.isoformat(),
            "recent_nav": [
                {"date": n.date.isoformat(), "nav": float(n.nav), "acc_nav": float(n.acc_nav)}
                for n in navs[-5:]  # last 5 days
            ],
        }
    except Exception as e:
        return {"error": str(e), "code": code}


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
