"""MCP tool: discover_funds — two-stage full-market fund discovery.

Stage 1: light-score all ~19,747 pool funds on 3 NavStore-free dims
         (consensus/peer/fee) → top 200.
Stage 2: enrich those 200 with risk_control + persistence (NavStore)
         and recompute with full 5-dim weights → top_n.
"""
from decimal import Decimal

from src.engine.risk_personalization import classify_fund_type, get_weights
from src.engine.screener import (
    ScreenConfig,
    score_funds_light,
    score_risk_control,
    score_consistency,
)

# How many Stage 1 survivors advance to Stage 2.
# 200 balances coverage vs Stage 2 NavStore latency.
_STAGE2_CANDIDATES = 200


def _get_or_load_pool_index():
    """Reuse screener's pool index loader (avoids double-fetch)."""
    from src.tools.screener import _get_or_load_pool_index as _loader
    return _loader()


def _get_or_load_category_averages():
    """Reuse screener's category averages loader."""
    from src.tools.screener import _get_or_load_category_averages as _loader
    return _loader()


def _get_nav_store():
    """Reuse screener's NavStore singleton."""
    from src.tools.screener import _get_nav_store as _loader
    return _loader()


def _enrich_peer_comparison(result: dict, fund_type: str) -> dict:
    """Add peer_comparison (category + avg 1y return). Reuses screener's."""
    from src.tools.screener import _enrich_peer_comparison as _enrich
    return _enrich(result, fund_type)


def discover_funds(
    risk_level: str,
    allowed_types: str = "",
    min_net_asset_value: float = 0,
    max_fee_rate: float = 0.03,
    top_n: int = 10,
) -> dict:
    """【全市场基金发现】从 19,747 只基金池中筛选并评分 top N。

    两阶段流水线:
      Stage 1: 用 3 维度(机构共识/同类业绩/费率)轻量打分全市场 → top 200
      Stage 2: 用 5 维度(加风控/持续性)全打分 → top N

    使用场景:
    - "帮我从全市场找最好的债基"
    - "发现规模>5亿的混合基金 top 10"
    - 替代网络搜索建候选池

    HOW TO USE:
    - risk_level: "conservative"|"moderate"|"aggressive" (影响评分权重)
    - allowed_types: 逗号分隔 "bond,mixed,index", 空=全部
    - min_net_asset_value: 最低规模(元), 默认0。注意: Stage 1 无法按规模过滤
      (PoolFund 无此字段)，此参数当前不生效。买入前请用 audit_single_fund 检查规模红线。
    - max_fee_rate: 最高费率, 默认0.03 (3%)
    - top_n: 返回前N只, 默认10

    RETURNS: {count, results[], stage1_evaluated, stage2_evaluated, personalized}
    - results: 按 score 降序, 含 5 维度评分 + warnings
    """
    if top_n < 0:
        top_n = 0

    # ── Build ScreenConfig ──────────────────────────────────────────
    types_set = frozenset(
        t.strip() for t in allowed_types.split(",") if t.strip()
    ) if allowed_types else frozenset({"stock", "bond", "mixed", "index", "money"})

    config = ScreenConfig(
        min_net_asset_value=Decimal(str(min_net_asset_value)),
        allowed_types=types_set,
        max_fee_rate=Decimal(str(max_fee_rate)),
    )

    # ── Coverage gate ───────────────────────────────────────────────
    nav_store = _get_nav_store()
    coverage = nav_store.coverage_report()
    if coverage["fund_count"] == 0:
        return {
            "count": 0,
            "results": [],
            "stage1_evaluated": 0,
            "stage2_evaluated": 0,
            "personalized": risk_level,
            "error": "NAV 数据库为空，请先运行回填: python3 -m src.data.sources.nav_store --backfill",
        }

    # ── Load pool + category averages ────────────────────────────────
    pool_index = _get_or_load_pool_index()
    cat_avg_data = _get_or_load_category_averages()
    # Production returns {"raw": ..., "broad": {...}} — use broad.
    # Direct {fund_type: {...}} form (e.g. test mocks) is used as-is.
    cat_avg = cat_avg_data.get("broad") or cat_avg_data if cat_avg_data else {}

    if not pool_index:
        return {
            "count": 0,
            "results": [],
            "stage1_evaluated": 0,
            "stage2_evaluated": 0,
            "personalized": risk_level,
        }

    # ── Stage 1: light-score full pool ───────────────────────────────
    stage1_results = score_funds_light(
        list(pool_index.values()), config, cat_avg, risk_level,
    )
    stage1_count = len(stage1_results)

    # ── Take top N candidates for Stage 2 ────────────────────────────
    candidates = stage1_results[:_STAGE2_CANDIDATES]

    # ── Stage 2: enrich with risk_control + persistence ──────────────
    final_results: list[dict] = []
    for light in candidates:
        pool_fund = pool_index.get(light.code)
        if pool_fund is None:
            continue

        fund_class = classify_fund_type(light.fund_type)
        full_weights = get_weights(fund_class, risk_level)
        dimensions = dict(light.dimension_breakdown)  # copy 3 Stage 1 dims

        warnings: list[str] = []

        # ── Add 2 NavStore dims (skip for money) ─────────────────────
        if fund_class != "money":
            nav_series = nav_store.get_nav_series(light.code)
            if len(nav_series) < 63:
                continue  # excluded — insufficient NAV
            dimensions["risk_control"] = score_risk_control(nav_series) * 5
            dimensions["persistence"] = score_consistency(nav_series) * 10

        # ── Recompute score with FULL weights ────────────────────────
        score = int(sum(dimensions[d] * full_weights[d] for d in full_weights))

        # ── Warnings (fee only — no net_asset_value/inception in PoolFund) ──
        if Decimal(str(pool_fund.fee)) > Decimal("0.015"):
            warnings.append(f"费率偏高 ({float(pool_fund.fee):.1%})")

        result = {
            "code": light.code,
            "name": light.name,
            "type": light.fund_type,
            "fund_type_class": fund_class,
            "net_asset_value": None,  # not available in PoolFund — use audit_single_fund for full check
            "fee_rate": float(pool_fund.fee),
            "inception_date": None,
            "score": score,
            "dimension_breakdown": dimensions,
            "warnings": warnings,
        }
        final_results.append(_enrich_peer_comparison(result, light.fund_type))

    # ── Sort by final score, take top_n ──────────────────────────────
    final_results.sort(key=lambda r: r["score"], reverse=True)
    top_results = final_results[:top_n]

    return {
        "count": len(top_results),
        "results": top_results,
        "stage1_evaluated": stage1_count,
        "stage2_evaluated": len(final_results),
        "personalized": risk_level,
    }
