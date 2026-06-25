# 09 — discover_funds MCP Tool Spec

## Motivation

Fortress has a full-market fund pool (`fetch_fund_pool` → 19,747 funds via akshare bulk APIs) with agency ratings and returns, but **no MCP tool exposes fund discovery**. `lookup_fund` verifies a single code; `screen_funds` scores a user-provided list (uses the pool internally only as a lookup index for ratings/category averages). The only way to build a candidate pool today is external web search, which introduces SEO/popularity bias and excludes niche funds with low media coverage.

This gap surfaced during a portfolio review: the user had to dispatch web-search agents to build a 15-fund candidate list, then score it with `screen_funds`. Funds that would have scored well but had low media exposure never entered consideration.

## Goal

Add a 17th MCP tool `discover_funds` that filters and ranks the full 19,747-fund pool by scoring criteria, returning the top N funds — no external data sourcing required.

## Tool Interface

```python
discover_funds(
    risk_level: str,                    # required: "conservative"|"moderate"|"aggressive"
    allowed_types: str = "",            # "bond,mixed,index" — "" = all 5 types
    min_net_asset_value: float = 0,     # default 0 — Stage 1 scoring handles ranking
    max_fee_rate: float = 0.03,        # default 3% — same as screen_funds
    top_n: int = 10,                    # return top 10 by full score
) -> dict
```

**Returns** (same shape as `screen_funds` for UI consistency):
```python
{
    "count": int,
    "results": [{
        "code", "name", "type", "fund_type_class",
        "net_asset_value", "fee_rate", "inception_date",
        "score", "dimension_breakdown", "warnings", "peer_comparison"
    }],
    "stage1_evaluated": int,   # diagnostic: how many funds entered Stage 1
    "stage2_evaluated": int,   # diagnostic: how many funds entered Stage 2
    "personalized": str,
}
```

## Two-Stage Pipeline

### Stage 1: Light scoring (all 19,747 funds, no NavStore)

Scores every fund in the pool on **3 of 5 dimensions** computable from `PoolFund` data alone (no NAV history lookup):

| Dimension | Source | NavStore needed? |
|---|---|---|
| institutional_consensus | 4 agency ratings (PoolFund) | ❌ |
| peer_performance | 5-period returns vs category avg (PoolFund) | ❌ |
| fee | fee_rate (FundInfo/PoolFund) | ❌ |
| risk_control | NAV volatility + drawdown | ✅ skipped |
| persistence | NAV return stability | ✅ skipped |

**Special case — money funds**: full scoring already uses only 3 dimensions (risk_control/persistence are N/A for money). For money funds, Stage 1 ≡ full score — zero information loss.

**Output**: ranked list of all scored funds → take **top 200** for Stage 2.

### Stage 2: Full scoring (top 200, with NavStore)

Calls existing `score_funds()` on the top 200 from Stage 1 — full 5-dimension scoring including risk_control and persistence (which need `nav_store.get_nav_series`).

**Output**: top `top_n` (default 10) by full score.

### Why two stages

- Stage 1 is **O(N) dictionary lookups + arithmetic** — milliseconds for 19,747 funds.
- Stage 2 is **O(200) NavStore queries** — each query reads a NAV series from SQLite. 200 queries ≈ 1-2 seconds; 19,747 would be minutes.
- This eliminates the survivorship bias of hard pre-filtering: any fund can reach Stage 2 if its 3 available dimensions are strong, regardless of scale or media exposure.

## Stage 1 Weight Scheme

**Approach**: reuse existing 9 weight sets from `get_weights(fund_class, risk_level)`, drop the 2 NavStore-dependent dimensions, renormalize the remaining 3 to sum to 100%.

### Renormalized weights

**active** (mixed/stock):

| risk_level | institutional_consensus | peer_performance | fee | dropped (risk_ctrl + persistence) |
|---|---|---|---|---|
| conservative | 45.5% | 18.2% | 36.4% | 45% |
| moderate | 35.7% | 35.7% | 28.6% | 30% |
| aggressive | 25.0% | 50.0% | 25.0% | 20% |

**passive** (index):

| risk_level | institutional_consensus | peer_performance | fee | dropped |
|---|---|---|---|---|
| conservative | 26.7% | 20.0% | 53.3% | 25% |
| moderate | 18.8% | 25.0% | 56.3% | 20% |
| aggressive | 11.8% | 29.4% | 58.8% | 15% |

**money**: unchanged (40/30/30, 35/35/30, 30/40/30) — Stage 1 ≡ full score.

### Why reuse + renormalize (not new weights)

1. **Zero new weight system** — DRY, no second matrix to maintain.
2. **Philosophy consistent** — Stage 1 is literally "full score with 2 dims zeroed", then renormalized. Same relative emphasis.
3. **Money funds zero loss** — 3/5 fund classes have no information loss.
4. **Dropped dims are the noisy ones** — risk_control and persistence depend on historical NAV, which is exactly what we're avoiding in Stage 1. The 3 remaining (agency ratings + returns + fee) are the more stable, agency-vetted signals — appropriate for a pre-filter.

### Renormalization is cosmetic for ranking

For Stage 1's purpose (select top 200), only relative order matters. Renormalization (dividing by sum of available weights) preserves order — it just scales scores to 0-100 for display. Implementation may skip renormalization and use raw weighted sums; ranking is identical.

## Exclusion Rules (align with existing `score_funds`)

Stage 1 inherits the same exclusions as `score_funds` (project principle: "数据缺失时排除基金，绝不捏造分数"):

| Condition | Action | Reason |
|---|---|---|
| Fund not in `pool_index` | exclude | no ratings/returns data |
| All 4 agency ratings = 0 | exclude | no institutional consensus (InsufficientDataError) |
| No category averages for fund type | exclude | can't compute peer_performance |
| All return periods = 0/missing | exclude | no returns data (InsufficientDataError) |

**Note**: this means unrated funds (no agency coverage) are excluded from Stage 1. This is consistent with full scoring and the project's no-fabrication principle. It IS a form of survivorship bias (new/small funds often lack ratings), but it's the project's established behavior, not a new bias introduced by this tool.

## Non-Goals

- **No RL-004 (concentration) check** — portfolio-level, requires `planned_amount`; user must still run `audit_single_fund` before buying any discovered fund.
- **No `planned_amount` parameter** — keeps tool about discovery, not portfolio context.
- **No hard-rule toggle** — defaults are audit-safe via scoring (unrated excluded, fee scored); no on/off switch (YAGNI).
- **No `min_inception_date` exposure** — `score_funds` already warns on inception < 1 year via warnings; let the 持续性 dimension penalize, don't hard-filter.

## Implementation

### New files
- `src/engine/screener.py` — add `score_funds_light()` (pure function, no I/O, scores PoolFund list on 3 dims)
- `src/tools/discover.py` — new MCP tool wrapping the two-stage pipeline
- `tests/engine/test_screener_light.py` — Stage 1 scoring tests
- `tests/tools/test_discover.py` — discover_funds tool tests

### Modified files
- `src/tools/server.py` — register `discover_funds` as Tool 17
- `CODEBUDDY.md` — update "16 个自描述工具" → "17 个"

### `score_funds_light` signature (engine layer)

```python
def score_funds_light(
    pool: list[PoolFund],
    config: ScreenConfig,
    category_averages: dict[str, dict[str, float]],
    risk_level: str = "moderate",
) -> list[ScreenResult]:
    """Stage 1 — score funds on 3 dims (consensus/peer/fee), no NavStore.

    Reuses score_institutional_consensus, score_peer_performance, _score_fee.
    Renormalized weights via get_weights(fund_class, risk_level).
    Same exclusion rules as score_funds.
    """
```

### `discover_funds` flow (tool layer)

1. Load `pool_index` via existing `_get_or_load_pool_index()` (cached singleton)
2. Load `category_averages` via existing `_get_or_load_category_averages()` (cached)
3. Build `ScreenConfig` from params (min_net_asset_value, allowed_types, max_fee_rate)
4. **Stage 1**: call `score_funds_light(list(pool_index.values()), config, cat_avg, risk_level)` → ranked list
5. Take top 200 → convert to `FundInfo` list
6. **Stage 2**: call `score_funds(top_200, config, nav_store, pool_index, cat_avg, risk_level)` → full scored list
7. Take top `top_n`, enrich with `peer_comparison`, return

### NavStore coverage gate

Reuse the existing coverage gate from `screen_funds` (lines 150-159 of `src/tools/screener.py`): if `nav_store.coverage_report()["fund_count"] == 0`, return an error directing the user to run backfill. Stage 2 cannot function without NAV data.

## Testing

### Stage 1 unit tests (`test_screener_light.py`)
- Scores a fund with high ratings → high institutional_consensus
- Excludes fund with all-4-ratings = 0
- Excludes fund missing from pool (defensive)
- Money fund: Stage 1 score ≈ full score (no risk_control/persistence)
- Renormalized weights sum to 100% per type×profile
- Ranking order preserved with/without renormalization

### Tool tests (`test_discover.py`)
- Returns top_n results sorted by score descending
- `allowed_types="bond"` → only bond funds in results
- `min_net_asset_value=5e8` → all results have NAV ≥ 5亿
- Empty pool → returns count=0 (not crash)
- NavStore empty → returns error directing to backfill
- Stage 2 reduces top 200 → top_n correctly
- Diagnostic fields (`stage1_evaluated`, `stage2_evaluated`) populated

### Integration
- End-to-end: `discover_funds(risk_level="conservative", allowed_types="bond", top_n=5)` returns 5 bond funds with full dimension_breakdown including risk_control and persistence.

## Open Questions (defer to implementation)

1. Should Stage 1 return a tuple of (score, fund) or reuse `ScreenResult`? — Reuse ScreenResult for consistency (it has dimension_breakdown + warnings).
2. Should the top-200 cutoff be configurable? — No (YAGNI); expose as module constant `_STAGE2_CANDIDATES = 200`.
3. Should `discover_funds` accept `min_inception_date`? — No (non-goal); let persistence dimension handle it.
