"""MCP tool: fund screening and ranking."""
import json
import os
from datetime import date
from decimal import Decimal
from typing import Any

from src.data.cache import MarketCache
from src.datatypes import FundInfo
from src.engine.category_benchmark import PERIODS, compute_category_averages
from src.engine.screener import ScreenConfig, apply_risk_personalization, screen_funds as _screen

_CACHE_DIR = os.environ.get("FORTRESS_DATA_DIR", "data")
_CATEGORY_CACHE_KEY = "category_averages:all"

# Module-level cache — loaded once, refreshed when SQLite cache expires
_category_averages: dict[str, dict[str, float]] | None = None


def _get_or_load_category_averages() -> dict[str, dict[str, float]]:
    """Return cached category averages, loading/computing on first call.

    Uses existing market_cache.db with 24h TTL. Falls back to computing
    from fund pool when cache is empty or expired.
    """
    global _category_averages

    # Try cache first
    cache = MarketCache(f"{_CACHE_DIR}/market_cache.db")
    cached_raw = cache.get(_CATEGORY_CACHE_KEY)
    if cached_raw is not None:
        try:
            _category_averages = json.loads(cached_raw)
            return _category_averages
        except json.JSONDecodeError:
            pass  # Corrupted cache → recompute

    if _category_averages is None:
        # Compute from fund pool (expensive, only on cache miss)
        try:
            from src.data.sources.fund_pool import fetch_fund_pool
            pool = fetch_fund_pool()
            _category_averages = compute_category_averages(pool)

            # Persist to cache
            cache.set(
                _CATEGORY_CACHE_KEY,
                json.dumps(_category_averages),
                ttl_seconds=86400,  # 24 hours
            )
        except Exception:
            # Fund pool unavailable → return empty, let caller handle
            _category_averages = {}

    return _category_averages


def _enrich_peer_comparison(
    result: dict,
    fund_type: str,
    nav_data: dict | None,
) -> dict:
    """Add peer_comparison dict to a screening result."""
    averages = _get_or_load_category_averages()
    cat_avg = averages.get(fund_type, {})

    # Compute fund's 1-year return from nav_data if available
    fund_ret_1y: float | None = None
    code = result.get("code", "")
    if nav_data and code in nav_data:
        nv = nav_data[code]
        if len(nv) > 1:
            prices = [float(v) for v in nv]
            if prices[0] > 0:
                fund_ret_1y = round((prices[-1] / prices[0] - 1) * 100, 2)

    category_avg_1y = round(cat_avg.get("ret_1y", 0.0), 2)
    excess_1y = round(fund_ret_1y - category_avg_1y, 2) if fund_ret_1y is not None else None

    result["peer_comparison"] = {
        "category": fund_type,
        "fund_return_1y": fund_ret_1y,
        "category_avg_1y": category_avg_1y,
        "excess_1y": excess_1y,
    }
    return result


def screen_funds(
    funds: list,
    min_net_asset_value: float = 0,
    allowed_types: str = "",
    max_fee_rate: float = 0.03,
    nav_data: dict | None = None,
    benchmark_data: dict | None = None,
    risk_level: str = "",
) -> dict:
    """Screen and rank a list of funds. v1 static scoring default; v2 when nav_data provided.

    Args:
        funds: List of fund dicts, each with:
            code, name, type, net_asset_value, fee_rate, inception_date ("YYYY-MM-DD").
        min_net_asset_value: Minimum fund size filter (CNY). 0 = no filter.
        allowed_types: Comma-separated fund types, e.g. "bond,mixed". Empty = all.
        max_fee_rate: Maximum acceptable fee rate (e.g. 0.015 = 1.5%).
        nav_data: Optional {code: [nav_values]} for v2 5-dimension scoring.
        benchmark_data: Optional {fund_type: [benchmark_navs]} for relative scoring.
        risk_level: Optional "conservative"|"moderate"|"aggressive" to personalize scores.
    """
    if not funds:
        return {"results": [], "count": 0}

    # Build FundInfo list
    fund_infos: list[FundInfo] = []
    errors: list[dict] = []
    for i, f in enumerate(funds):
        try:
            fund_infos.append(FundInfo(
                code=str(f["code"]),
                name=str(f.get("name", "")),
                type=str(f.get("type", "mixed")),
                net_asset_value=Decimal(str(f.get("net_asset_value", 0))),
                fee_rate=Decimal(str(f.get("fee_rate", 0.015))),
                inception_date=date.fromisoformat(str(f.get("inception_date", "2020-01-01"))),
            ))
        except (KeyError, ValueError, TypeError) as e:
            errors.append({"index": i, "fund": f.get("code", "?"), "error": str(e)})

    if not fund_infos:
        return {"results": [], "count": 0, "errors": errors}

    # Build ScreenConfig
    types_set = frozenset(
        t.strip() for t in allowed_types.split(",") if t.strip()
    ) if allowed_types else frozenset({"stock", "bond", "mixed", "index", "money"})

    config = ScreenConfig(
        min_net_asset_value=Decimal(str(min_net_asset_value)),
        allowed_types=types_set,
        max_fee_rate=Decimal(str(max_fee_rate)),
    )

    # Run screening
    results = _screen(fund_infos, config, nav_data, benchmark_data=benchmark_data)

    # ── Risk-level personalization ────────────────────────────────────
    if risk_level and nav_data:
        results = apply_risk_personalization(results, nav_data, risk_level)

    # ── Build peer comparison context ──────────────────────────────────
    averages = _get_or_load_category_averages()
    have_peers = bool(averages)

    return {
        "count": len(results),
        "results": [
            _enrich_peer_comparison(
                {
                    "code": r.fund.code,
                    "name": r.fund.name,
                    "type": r.fund.type,
                    "net_asset_value": float(r.fund.net_asset_value),
                    "fee_rate": float(r.fund.fee_rate),
                    "inception_date": r.fund.inception_date.isoformat(),
                    "score": r.score,
                    "warnings": list(r.warnings),
                },
                r.fund.type,
                nav_data,
            )
            for r in results
        ],
        "errors": errors if errors else None,
        "personalized": risk_level or None,
        "category_averages_available": have_peers,
    }
