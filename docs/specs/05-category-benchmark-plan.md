# Implementation Plan: Category Peer Benchmark (同类平均对比)

## Overview

Add category peer average comparison to fortress screening and reports.
Data source: fund_pool's 19,747 pre-computed fund returns. Zero new dependencies.

## Architecture Decisions

- **Cache in same SQLite as market_cache.db**: avoids introducing new storage. Category averages change slowly (daily pool refresh is sufficient). Use existing MarketCache.
- **Engine layer function (zero I/O)**: `compute_category_averages()` operates on a list of PoolFunds, following the existing pattern of `score_performance` etc.
- **Tool layer integration point**: `screen_funds` MCP tool adds `peer_comparison` dict to each result after calling the engine screener. Category averages are loaded once at tool-level, cached in module variable.
- **Report integration**: `context.py` reads `peer_comparison` from existing `health_check` or new top-level field, passes to Jinja2 template.
- **Module-level cache lifetime**: averages are computed on first call, refreshed when cache expires. No need for startup loading.

## Task List

### Phase 1: Engine + Tests

- [ ] **Task 1**: Create `src/engine/category_benchmark.py` with `compute_category_averages()`

  **Acceptance criteria:**
  - Accepts `list[PoolFund]`, returns `{fund_type: {period: avg_pct}}`
  - Handles empty pool (returns {})
  - Handles single-fund category (returns that fund's value as average)
  - Filters funds with zero returns to avoid skew
  - All 5 periods: ret_1m, ret_3m, ret_6m, ret_1y, ret_3y

  **Verification:**
  - Tests pass: `python3 -m pytest tests/engine/test_category_benchmark.py`

  **Dependencies:** None

  **Files likely touched:** `src/engine/category_benchmark.py` (new), `tests/engine/test_category_benchmark.py` (new)

  **Estimated scope:** Small (1-2 files)

---

- [ ] **Task 2**: Create tests for `compute_category_averages`

  **Acceptance criteria:**
  - `test_multi_fund_average`: 3 bond funds (ret_1y=2,4,6) → avg=4.0
  - `test_empty_pool_returns_empty`: returns {}
  - `test_single_category`: only bond funds present, others empty
  - `test_zero_returns_filtered`: funds with ret_1y=0 excluded from mean
  - `test_all_periods_present`: result has all 5 period keys

  **Verification:**
  - All 5 tests pass

  **Dependencies:** Task 1

  **Files:** `tests/engine/test_category_benchmark.py` (same as Task 1)

  **Estimated scope:** Small (1 file)

### Checkpoint: Engine
- [ ] `compute_category_averages` works, 5 tests pass
- [ ] Existing screener tests still pass (23/23)

---

### Phase 2: Tool Integration

- [ ] **Task 3**: Add category averages caching + integrate into `screen_funds` output

  **Acceptance criteria:**
  - Module-level `_category_averages: dict | None` in `tools/screener.py`
  - `_get_or_load_averages()` loads from cache or computes from pool
  - `screen_funds()` appends `peer_comparison` to each result dict
  - `peer_comparison` contains: `category`, `fund_return_1y`, `category_avg_1y`, `excess_1y`
  - Fund return computed from nav_data when available; uses fund pool data otherwise

  **Verification:**
  - Manually test with real fund data: run screen_funds with nav_data, verify peer_comparison present

  **Dependencies:** Task 1 (engine function exists)

  **Files:** `src/tools/screener.py`

  **Estimated scope:** Medium (3-5 files — also touches cache layer)

---

- [ ] **Task 4**: Add cache persistence layer for category averages

  **Acceptance criteria:**
  - Category averages stored in existing `market_cache.db` under key `category_averages:all`
  - TTL: 86400 (24 hours)
  - Stored as JSON: `{"bond": {"ret_1y": 5.4, ...}, "mixed": {...}}`
  - `_get_or_load_averages()` checks cache first, falls back to pool compute

  **Verification:**
  - First call: computes from pool, stores in cache
  - Second call within TTL: returns cached value
  - Expired cache: recomputes

  **Dependencies:** Task 3

  **Files:** `src/tools/screener.py` (inline in Task 3), uses existing `src/data/cache.py` MarketCache

  **Estimated scope:** Small

### Checkpoint: ScreenFunds Integration
- [ ] `screen_funds` output includes `peer_comparison` for every result
- [ ] Category averages are cached and lazy-loaded

---

### Phase 3: Report Integration

- [ ] **Task 5**: Add `peer_comparison` to report context and HTML template

  **Acceptance criteria:**
  - `context.py` passes `peer_comparisons` list to Jinja2
  - `report.html` adds "同类对比" section (after "组合健康度", before "注意事项")
  - Each fund row shows: name, 1y return, category avg, excess with color
  - Green (跑赢) / Red (跑输) CSS classes

  **Verification:**
  - Generate a test report with `get_advice(path="C")`, verify section appears
  - Visual check: green for outperformance, red for underperformance

  **Dependencies:** Tasks 3-4

  **Files:** `src/report/context.py`, `src/report/templates/report.html`

  **Estimated scope:** Small (2 files)

### Checkpoint: Complete
- [ ] All acceptance criteria met
- [ ] Ready for review (code-review-and-quality)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| fund_pool build is slow (>2 min for 19K funds) | High | Cache averages; only rebuild when pool is refreshed |
| Category averages inaccurate with null data | Medium | Filter zero/N/A returns; document filter logic |
| `screen_funds` output size grows significantly | Low | `peer_comparison` adds ~100 bytes per result (negligible) |

## Open Questions

- Should the category average EXCLUDE the fund being evaluated? → **No**, simpler to include; with 1000+ funds per category, self-inclusion bias is negligible.
