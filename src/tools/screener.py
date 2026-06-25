"""MCP tool: fund screening and ranking — unified 5-dimension scoring."""
import json
import os
from datetime import date
from decimal import Decimal

from src.data.cache import MarketCache
from src.datatypes import FundInfo
from src.engine.category_benchmark import compute_category_averages
from src.engine.risk_personalization import classify_fund_type
from src.engine.screener import ScreenConfig, score_funds

_CACHE_DIR = os.environ.get("FORTRESS_DATA_DIR", "data")
_CATEGORY_CACHE_KEY = "category_averages:all"

# Module-level singletons — lazy-init on first use
_category_averages: dict | None = None
_pool_index: dict[str, object] | None = None
_nav_store: object | None = None


def _get_nav_store():
    """Return module-level NavStore singleton (lazy-init)."""
    global _nav_store
    if _nav_store is None:
        from src.data.sources.nav_store import NavStore
        _nav_store = NavStore(os.path.join(_CACHE_DIR, "market_cache.db"))
    return _nav_store


def _get_or_load_pool_index() -> dict[str, object]:
    """Return cached {code: PoolFund} index, loading from fund pool on first call.

    Same caching pattern as _get_or_load_category_averages.
    """
    global _pool_index
    if _pool_index is not None:
        return _pool_index
    try:
        from src.data.sources.fund_pool import fetch_fund_pool
        pool = fetch_fund_pool(skip_filters=True)  # 大而全 — no filtering
        _pool_index = {f.code: f for f in pool}
    except Exception:
        _pool_index = {}
    return _pool_index


def _get_or_load_category_averages() -> dict[str, dict[str, float]]:
    """Return cached category averages, loading/computing on first call."""
    global _category_averages

    cache = MarketCache(f"{_CACHE_DIR}/market_cache.db")
    cached_raw = cache.get(_CATEGORY_CACHE_KEY)
    if cached_raw is not None:
        try:
            _category_averages = json.loads(cached_raw)
            return _category_averages
        except json.JSONDecodeError:
            pass

    if _category_averages is None:
        try:
            from src.data.sources.fund_pool import fetch_fund_pool
            pool = fetch_fund_pool()
            raw = compute_category_averages(pool, group_by="raw")
            broad = compute_category_averages(pool, group_by="broad")
            _category_averages = {"raw": raw, "broad": broad}
            cache.set(_CATEGORY_CACHE_KEY, json.dumps(_category_averages), ttl_seconds=86400)
        except Exception:
            _category_averages = {}

    return _category_averages


def _enrich_peer_comparison(result: dict, fund_type: str) -> dict:
    """Add peer_comparison dict to a screening result."""
    averages = _get_or_load_category_averages()
    raw = averages.get("raw", {}) if averages else {}
    broad = averages.get("broad", {}) if averages else {}

    cat_avg = raw.get(fund_type) or broad.get(fund_type) or {}
    category_avg_1y = round(cat_avg.get("ret_1y", 0.0), 2)

    result["peer_comparison"] = {
        "category": fund_type,
        "category_avg_1y": category_avg_1y,
    }
    return result


def screen_funds(
    funds: list,
    min_net_asset_value: float = 0,
    allowed_types: str = "",
    max_fee_rate: float = 0.03,
    risk_level: str = "",
) -> dict:
    """筛选并评分基金列表 — 统一 5 维度加权评分。

    5 dimensions (each 0-100, weighted by fund-type × risk-profile):
    机构共识 / 同类业绩 / 风控 / 持续性 / 费率

    WHEN TO USE:
    - 用户问"哪些基金最好"、"帮我选基金"
    - 拿到 lookup_fund 结果后，做横向比较
    - 配置方案确定后，筛选具体产品

    HOW TO USE:
    - funds: 基金信息列表，每项含 code, name, type, net_asset_value, fee_rate, inception_date
    - min_net_asset_value: 最低规模过滤（元），默认0不过滤
    - allowed_types: 逗号分隔，如 "bond,mixed"，空=全部
    - max_fee_rate: 最高可接受费率，默认 0.03 (3%)
    - risk_level: "conservative"|"moderate"|"aggressive"，空=moderate

    RETURNS: {count, results[{code, name, type, score, dimension_breakdown, warnings[]}]}
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

    # ── Coverage gate: refuse if NavStore is empty ───────────────────
    nav_store = _get_nav_store()
    coverage = nav_store.coverage_report()
    if coverage["fund_count"] == 0:
        return {
            "count": 0,
            "results": [],
            "errors": errors if errors else None,
            "error": "NAV 数据库为空，请先运行回填: python3 -m src.data.sources.nav_store --backfill",
        }

    # ── Build pool_index + category_averages ─────────────────────────
    pool_index = _get_or_load_pool_index()
    cat_avg_data = _get_or_load_category_averages()
    cat_avg_dict = cat_avg_data.get("broad", {}) if cat_avg_data else {}

    # ── Run unified scoring ──────────────────────────────────────────
    results = score_funds(
        fund_infos, config, nav_store, pool_index, cat_avg_dict,
        risk_level=risk_level or "moderate",
    )

    # ── Build output with dimension breakdown ─────────────────────────
    have_peers = bool(cat_avg_data)

    return {
        "count": len(results),
        "results": [
            _enrich_peer_comparison(
                {
                    "code": r.fund.code,
                    "name": r.fund.name,
                    "type": r.fund.type,
                    "fund_type_class": classify_fund_type(r.fund.type),
                    "net_asset_value": float(r.fund.net_asset_value),
                    "fee_rate": float(r.fund.fee_rate),
                    "inception_date": r.fund.inception_date.isoformat(),
                    "score": r.score,
                    "dimension_breakdown": r.dimension_breakdown,
                    "warnings": list(r.warnings),
                },
                r.fund.type,
            )
            for r in results
        ],
        "errors": errors if errors else None,
        "personalized": risk_level or None,
        "category_averages_available": have_peers,
    }
