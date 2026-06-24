# Spec: Category Peer Benchmark (同类平均对比)

## Objective

Fortress fund screening and reports currently score funds on absolute metrics only.
A fund can score 79/100 while underperforming its peers by 4%. This spec adds
**category peer average comparison** so every recommendation includes context:
"Your fund returned +1.4%, the bond fund average returned +5.4%."

**User story**: As an investor running `check_health` or `screen_funds`, I want to see
how my funds compare to their peers (same category average), so I can distinguish
"good in absolute terms" from "good relative to alternatives."

## Assumptions

1. Fund pool 5-category classification (stock/bond/mixed/index/money) is meaningful
   enough for peer comparison, matching Alipay's default granularity
2. Category averages change slowly (daily refresh is sufficient)
3. Fund pool data is built periodically and cached in SQLite (existing pattern from `market_cache.db`)

## Tech Stack

Pure Python, extending existing fortress engine + tools + report modules.
No new dependencies.

## Commands

```
Build:  python3 -m src.data.sources.fund_pool  # rebuild pool (periodic)
Test:   python3 -m pytest tests/engine/test_category_benchmark.py
All:    python3 -m pytest tests/
```

## Project Structure (changes)

```
src/
├── engine/
│   └── category_benchmark.py    ← NEW: compute_category_averages(), cache layer
├── tools/
│   └── screener.py              ← MODIFY: add peer_comparison to output
└── report/
    ├── context.py               ← MODIFY: add category comparison to report context
    └── templates/report.html    ← MODIFY: add "同类对比" section
tests/
└── engine/
    └── test_category_benchmark.py ← NEW: unit + integration tests
```

## Code Style

Follow existing fortress conventions:
- engine/ layer: zero I/O pure functions, `Decimal` for amounts
- tools/ layer: MCP input/output serialization only
- `_compute_metrics()` pattern for shared helpers (established in screener refactor)
- Type hints on all public functions

## Design

### compute_category_averages()

```python
# src/engine/category_benchmark.py — zero I/O
def compute_category_averages(
    fund_pool: list[PoolFund],
) -> dict[str, dict[str, float]]:
    """Return {fund_type: {period: avg_return_pct}} for 5 periods."""
    ...
```

- Groups 19,747 PoolFunds by `fund_type` (5 groups)
- Computes arithmetic mean of `ret_1m`, `ret_3m`, `ret_6m`, `ret_1y`, `ret_3y` per group
- Filters out funds with zero/unrated returns to avoid skew

### Cache Layer

- SQLite table `category_averages(type, period, avg_return, computed_at)` 
- Column names match existing `market_cache.db` conventions
- MCP server loads averages at startup, refreshes when pool is rebuilt

### screen_funds Integration

Each result dict gains `peer_comparison`:

```python
{
    "code": "217022",
    "name": "招商产业债券",
    "score": 72,
    ...existing fields...,
    "peer_comparison": {
        "category": "bond",
        "fund_return_1y": 1.43,
        "category_avg_1y": 5.40,
        "excess_1y": -3.97   # fund - category average
    }
}
```

### Report Integration

Path C diagnostic report gains a "同类对比" section showing:
- Fund name, 1y return, category average, excess
- Visual indicator: green for outperformance, red for underperformance

## Testing Strategy

- Unit tests: `compute_category_averages()` with synthetic PoolFund lists
- Integration tests: verify `screen_funds` output includes `peer_comparison` when averages available
- Edge cases: empty pool, single fund per type, null returns, zero returns

## Boundaries

- **Always do**: Compute from fund pool data only (no external API)
- **Always do**: Cache results, refresh when pool changes
- **Ask first**: Changing fund type classification granularity
- **Ask first**: Adding external benchmark indices (中证全债 etc.)
- **Never do**: Modify fund_pool.py's data model

## Success Criteria

- [ ] `screen_funds` output includes `peer_comparison` for every fund with category data
- [ ] Report HTML shows "同类对比" section when diagnostic completed
- [ ] All new functions have tests (≥ 5 test cases)
- [ ] Existing 23/23 screener tests still pass
- [ ] Category averages are cached (computed once, not per-request)

## Open Questions

- Should we exclude the fund itself from the category average when computing peer comparison?
  (Currently: include. Simpler, and impact on average with 1000+ funds per category is negligible.)
