# Task Breakdown: Unified Fund Scoring + NAV Storage Layer

Reference: `docs/specs/06-unified-scoring-spec.md` (spec) · `docs/specs/07-unified-scoring-plan.md` (plan)

Task template: each task has Acceptance (what must be true when done) · Verify (how to confirm) ·
Files (what's touched) · Dependencies (what must be done first). Ordered by dependency, not
importance. No task touches >5 files.

---

## Phase 1: Engine Pure Functions (parallel — 1a/1b/1c independent)

### Task 1a: Institutional Consensus module

- [ ] **Task**: Create `src/engine/institutional_consensus.py` — `score_institutional_consensus()`
  + `InsufficientDataError`. Zero I/O, pure function. Takes a ratings dict
  `{"morningstar": 4, "shanghai": 3, "zhaoshang": 0, "jiAn": 5}`, returns 0-100. All-zero ratings
  → raise `InsufficientDataError("无机构评级")`.
- **Acceptance**:
  - `score_institutional_consensus({"morningstar":5,"shanghai":5,"zhaoshang":5,"jiAn":5})` == 100
  - `score_institutional_consensus({"morningstar":0,"shanghai":0,"zhaoshang":0,"jiAn":0})` raises
  - Only non-zero ratings count in the average (0 = unrated, not 0-score)
  - 2 of 4 unrated → averages the other 2, not penalized
  - `InsufficientDataError` is a new exception type in `src/engine/` (or `src/datatypes.py`)
- **Verify**: `python3 -m pytest tests/engine/test_institutional_consensus.py -v` — ≥5 test cases
  (all-rated, all-unrated, partial-unrated, single-rated, boundary 0/5)
- **Files**: `src/engine/institutional_consensus.py` (new), `tests/engine/test_institutional_consensus.py` (new), `src/datatypes.py` (add exception) or `src/engine/__init__.py`
- **Dependencies**: None

### Task 1b: Peer Scoring module

- [ ] **Task**: Create `src/engine/peer_scoring.py` — `score_peer_performance()` + `PERIOD_WEIGHTS`.
  Zero I/O. Takes `fund_returns: dict[str,float]`, `category_averages: dict[str,float]`,
  optional `period_weights`. Returns 0-100 (50 = peer average, linear clamp). Uses
  `compute_category_averages` output shape (existing).
- **Acceptance**:
  - Fund exactly at category average → 50
  - Fund +10pp excess (weighted) → 70; Fund -10pp → 30
  - Clamps to [0, 100] on extreme excess
  - Missing period in `fund_returns` → treated as 0 excess for that period (graceful)
  - Default `PERIOD_WEIGHTS` sums to 1.0: 1m=0.10, 3m=0.15, 6m=0.20, 1y=0.35, 3y=0.20
- **Verify**: `python3 -m pytest tests/engine/test_peer_scoring.py -v` — ≥5 test cases
  (at-average, outperforms, underperforms, clamps, missing-period)
- **Files**: `src/engine/peer_scoring.py` (new), `tests/engine/test_peer_scoring.py` (new)
- **Dependencies**: None

### Task 1c: Risk Personalization weight tables

- [ ] **Task**: Create `src/engine/risk_personalization.py` — `WEIGHTS` dict (9 combinations:
  3 fund-type classes × 3 risk profiles) + `get_weights(fund_type_class, risk_level) -> dict` +
  `classify_fund_type(fund_type: str) -> str` ("active"|"passive"|"money"). Each weight row sums
  to 1.0. Extract existing `apply_risk_personalization` logic from `screener.py` and adapt as a
  post-score risk-control adjustment (preserve existing conservative/aggressive behavior).
- **Acceptance**:
  - `WEIGHTS["active"]["conservative"]` has 5 keys summing to 1.0
  - `WEIGHTS["passive"]["aggressive"]["fee"]` == 0.50 (fee dominates passive)
  - `WEIGHTS["money"]` has 3 keys (no risk_control, no persistence) summing to 1.0
  - `classify_fund_type("bond")` == "active"; `classify_fund_type("index")` == "passive";
    `classify_fund_type("money")` == "money"
  - Invalid `risk_level` raises `ValueError`
- **Verify**: `python3 -m pytest tests/engine/test_risk_personalization.py -v` — ≥6 test cases
  (each fund-type class × each profile row-sum=1.0, classify mapping, invalid input)
- **Files**: `src/engine/risk_personalization.py` (new), `tests/engine/test_risk_personalization.py` (new)
- **Dependencies**: None

### Checkpoint 1
- [ ] All 3 modules' tests pass
- [ ] `python3 -m pytest tests/` — existing 304 tests still pass (no regressions from new files)
- [ ] `grep -r "import\|open\|requests\|akshare" src/engine/institutional_consensus.py src/engine/peer_scoring.py src/engine/risk_personalization.py` — no I/O imports

---

## Phase 2: NAV Storage Layer

### Task 2a: NavStore schema + read/query methods

- [ ] **Task**: Create `src/data/sources/nav_store.py` — `NavStore` class initialized with a SQLite
  path (default: existing `market_cache.db`). Create `fund_nav` + `nav_backfill_progress` tables
  (DDL from spec §1). Implement `get_nav_series(code, days=750)`, `get_latest_date()`,
  `coverage_report()`, `stats()`. No akshare calls yet — pure DB operations.
- **Acceptance**:
  - Tables created idempotently (CREATE IF NOT EXISTS)
  - `get_nav_series` returns list[float] oldest-first; empty list if no data
  - `coverage_report()` returns `{total_pool, with_nav, missing_nav, latest_date, coverage_rate}`
  - `stats()` returns fund count + date range
  - Works with temp SQLite DB in tests
- **Verify**: `python3 -m pytest tests/data/test_nav_store.py::TestNavStoreRead -v`
- **Files**: `src/data/sources/nav_store.py` (new), `tests/data/test_nav_store.py` (new)
- **Dependencies**: None (uses existing `src/data/cache.py` patterns for DB path)

### Task 2b: Backfill method (concurrent, idempotent, resumable)

- [ ] **Task**: Add `NavStore.backfill(codes, period="3年", max_workers=20) -> BackfillReport` to
  `nav_store.py`. Uses `ak.fund_open_fund_info_em(symbol, period)` per fund via
  `ThreadPoolExecutor`. `INSERT OR IGNORE` on (code, nav_date). Updates
  `nav_backfill_progress` per code (pending→done/failed). Resumable: skips codes already "done".
  Returns `{fetched, skipped, failed, point_count}`.
- **Acceptance**:
  - Re-running `backfill` on same codes → all skipped (idempotent)
  - Interrupted backfill → resume continues from last "pending" code
  - Failed fund (invalid code) → status="failed", doesn't crash the batch
  - `max_workers` capped at 20 (akshare rate-limit safety)
  - Mock akshare in unit tests; do a 5-fund live smoke test manually
- **Verify**: `python3 -m pytest tests/data/test_nav_store.py::TestBackfill -v` (mocked) +
  manual: `python3 -c "from src.data.sources.nav_store import NavStore; NavStore().backfill(['217022','675091'])"`
- **Files**: `src/data/sources/nav_store.py` (modify), `tests/data/test_nav_store.py` (modify)
- **Dependencies**: Task 2a

### Task 2c: Update method (gap detection + tiered recovery)

- [ ] **Task**: Add `NavStore.update() -> UpdateReport` + trading-day awareness via
  `ak.tool_trade_date_hist_sina()` (cached). Gap = latest DB date vs latest trading date.
  - gap ≤ 2 trading days → `ak.fund_open_fund_daily_em()` bulk append (1 HTTP)
  - gap 3-30 → mark `recovery_needed=True`, lazy-recover happens on `get_nav_series` miss
  - gap > 30 → log warning, set `recovery_needed=True`, defer to manual `backfill`
  Add `_lazy_recover(code)` — per-fund `period="1月"` fetch on cache miss during recovery mode.
- **Acceptance**:
  - Weekend gap (Fri→Mon) detected as 1 trading day, not 3 calendar days
  - ≤2-day gap → exactly 1 `fund_open_fund_daily_em` call, all funds appended
  - 3-30 day gap → `recovery_needed` flag set; `get_nav_series(missing_code)` triggers lazy fetch
  - >30 day gap → warning logged, no auto-fetch
  - Trading-date list cached (not re-fetched every `update()` call)
- **Verify**: `python3 -m pytest tests/data/test_nav_store.py::TestUpdate -v` (mocked akshare)
- **Files**: `src/data/sources/nav_store.py` (modify), `tests/data/test_nav_store.py` (modify)
- **Dependencies**: Task 2b

### Checkpoint 2
- [ ] nav_store all tests pass (mocked akshare)
- [ ] Manual 5-fund live backfill works end-to-end
- [ ] Gap detection: simulate by inserting old date, verify correct tier
- [ ] `python3 -m pytest tests/` — full suite green

---

## Phase 3: Unified Screener (rewrite)

### Task 3a: Unified score_funds signature + fund-type classification + exclusion

- [ ] **Task**: Rewrite `src/engine/screener.py` top-level: new `score_funds()` signature (per
  spec §2, takes `nav_store`, `pool_index`, `category_averages`, `risk_level`). Remove `use_v2`
  branch. Add `_classify_fund_type()` → "active"|"passive"|"money" (delegates to
  `risk_personalization.classify_fund_type`). Implement exclusion logic: catch
  `InsufficientDataError` from consensus; check NAV < 63 points → exclude with warning.
  Keep existing `_score_static`, `score_performance`, `score_risk_control`, `score_consistency`,
  `score_manager` as internal helpers (reused, not deleted).
- **Acceptance**:
  - No `use_v2` variable; no `if use_v2` branch in the file
  - `grep "use_v2\|v1.*static\|nav_data" src/engine/screener.py` returns nothing
  - Fund with all-zero ratings → excluded, warning in result
  - Fund with NAV < 63 points → excluded, warning in result
  - Fund age < 1 year → scored, warning appended
  - `score_funds` returns `list[ScreenResult]` where each result has a `dimension_breakdown` dict
- **Verify**: `python3 -m pytest tests/engine/test_unified_screener.py::TestExclusion -v`
- **Files**: `src/engine/screener.py` (rewrite), `tests/engine/test_unified_screener.py` (new)
- **Dependencies**: Tasks 1a, 1c, 2a (for types/interfaces; nav_store mocked in tests)

### Task 3b: Wire 5 scoring dimensions

- [ ] **Task**: In `score_funds()`, compute all 5 dimensions per fund:
  - Institutional consensus: call `score_institutional_consensus(ratings)` from PoolFund
  - Peer performance: call `score_peer_performance(fund_returns, category_averages)`
  - Risk control: call existing `score_risk_control(nav_series)` — refactor to accept
    `list[float]` from `nav_store.get_nav_series()` instead of `nav_data[code]`
  - Persistence: call existing `score_consistency(nav_series)` — same refactor
  - Fee: new `score_fee(fee: Decimal) -> int` — maps fee rate to 0-100 (lower fee = higher score)
  Money funds skip risk_control + persistence (structurally N/A, not missing).
- **Acceptance**:
  - Each dimension returns 0-100
  - `score_fee(Decimal("0.0015"))` (0.15%) → high score; `score_fee(Decimal("0.03"))` (3%) → low
  - Money fund → only 3 dimensions computed, no crash on missing NAV
  - `dimension_breakdown` dict has all computed dimension scores for transparency
- **Verify**: `python3 -m pytest tests/engine/test_unified_screener.py::TestDimensions -v`
- **Files**: `src/engine/screener.py` (modify), `tests/engine/test_unified_screener.py` (modify)
- **Dependencies**: Task 3a, Task 1b (peer_scoring)

### Task 3c: Apply personalized weights + final score

- [ ] **Task**: In `score_funds()`, after dimensions computed, look up weights via
  `get_weights(fund_type_class, risk_level)`. Compute final = weighted sum. Preserve existing
  `apply_risk_personalization` conservative/aggressive risk-control tweak as a pre-weight
  adjustment on the risk_control dimension. Sort results by final score descending.
- **Acceptance**:
  - Same fund, different `risk_level` → different final score (weights differ)
  - Same fund, same `risk_level`, different fund_type → different weights applied
  - All 9 weight combinations exercised in tests
  - Results sorted by score descending
  - `apply_risk_personalization` old behavior preserved for conservative (penalize high vol) and
    aggressive (reward high vol) — ported, not dropped
- **Verify**: `python3 -m pytest tests/engine/test_unified_screener.py::TestWeights -v` — test all
  9 combinations produce valid scores
- **Files**: `src/engine/screener.py` (modify), `tests/engine/test_unified_screener.py` (modify),
  `src/engine/risk_personalization.py` (adjust if extraction needs it)
- **Dependencies**: Task 3b, Task 1c

### Task 3d: Port existing screener test assertions

- [ ] **Task**: Read `tests/engine/test_screener.py` + `tests/engine/test_screener_v2.py`. For each
  assertion that tests preserved behavior (static scoring formula, warning generation, sort order,
  hard filters), port to `test_unified_screener.py`. Delete the two old files only after all
  ported assertions pass. Assertions testing removed behavior (v1/v2 split, nav_data param) are
  dropped with a comment noting why.
- **Acceptance**:
  - Every preserved-behavior assertion from old tests exists in `test_unified_screener.py`
  - Old files deleted (not left as dead code)
  - A comment block at top of `test_unified_screener.py` lists what was ported vs dropped
- **Verify**: `python3 -m pytest tests/engine/test_unified_screener.py -v` — all ported tests pass
- **Files**: `tests/engine/test_unified_screener.py` (modify), `tests/engine/test_screener.py`
  (delete), `tests/engine/test_screener_v2.py` (delete)
- **Dependencies**: Task 3c

### Checkpoint 3
- [ ] `grep "use_v2\|nav_data\|benchmark_data" src/engine/screener.py` — empty
- [ ] `python3 -m pytest tests/engine/ -v` — all engine tests pass
- [ ] `python3 -m pytest tests/` — full suite green (304 baseline maintained or improved)
- [ ] Old `test_screener.py` + `test_screener_v2.py` deleted

---

## Phase 4: Tool Layer + Report

### Task 4a: Tool layer — drop params, NavStore singleton, coverage gate

- [ ] **Task**: Modify `src/tools/screener.py` — remove `nav_data` and `benchmark_data`
  parameters from `screen_funds()`. Add module-level `NavStore` singleton (lazy-init). Call
  `nav_store.coverage_report()` at entry; if `coverage_rate == 0`, raise with backfill
  instructions. Pass `nav_store` + `pool_index` to engine `score_funds()`. Update docstring
  (remove v1/v2 mentions). Mirror the same param changes in `src/tools/server.py` MCP tool
  definition + `src/tools/a2a_adapter.py` schema.
- **Acceptance**:
  - `screen_funds()` signature has no `nav_data`, no `benchmark_data`
  - Empty nav_store → clear error message with backfill command
  - Non-empty nav_store → delegates to engine `score_funds`, returns results with
    `peer_comparison` + `dimension_breakdown`
  - MCP tool docstring updated (no v1/v2 mention)
- **Verify**: `python3 -m pytest tests/tools/test_screener_tool.py -v` + manual MCP call
- **Files**: `src/tools/screener.py` (modify), `src/tools/server.py` (modify),
  `src/tools/a2a_adapter.py` (modify), `tests/tools/test_screener_tool.py` (new/modify)
- **Dependencies**: Task 3d (engine stable)

### Task 4b: Report context — dimension breakdown + weights

- [ ] **Task**: Modify `src/report/context.py` — pass `dimension_breakdown` (per fund) and
  `active_weights` (the weight table used) + `fund_type_class` label to the Jinja2 template.
  Source these from the `screen_funds` result shape (each result now carries
  `dimension_breakdown`).
- **Acceptance**:
  - Template context has `dimension_breakdowns` list and `active_weights` dict
  - Each entry in `dimension_breakdowns` has fund code/name + 5 (or 3 for money) dimension scores
  - Fund type class label ("主动"/"被动"/"货币") included per fund
- **Verify**: `python3 -m pytest tests/report/test_context.py -v` (or manual render check)
- **Files**: `src/report/context.py` (modify), `tests/report/test_context.py` (new/modify)
- **Dependencies**: Task 4a (result shape finalized)

### Task 4c: Report template — §7.5 dimension table

- [ ] **Task**: Modify `src/report/templates/report.html` §7.5 — replace 1y-only peer table with a
  5-dimension breakdown table per fund. Columns: 机构共识/同类业绩/风控/持续性/费率 + 综合分.
  Show active weight row beneath. Label fund type class (主动/被动/货币). Money funds show 3
  columns (风控/持续性 greyed out with "N/A" + reason).
- **Acceptance**:
  - Table renders 5 dimensions for active/passive funds, 3 for money funds
  - Money fund rows show "N/A (摊余成本法)" for risk/persistence columns
  - Active weight table shown (so user sees which profile was used)
  - No broken Jinja2; template renders without error on test data
- **Verify**: Manual render with synthetic context; visual check of HTML output
- **Files**: `src/report/templates/report.html` (modify)
- **Dependencies**: Task 4b

### Checkpoint 4 (final)
- [ ] End-to-end: `screen_funds` MCP tool returns results with dimension breakdown
- [ ] Report renders §7.5 with 5-dimension table
- [ ] `python3 -m pytest tests/` — full suite green
- [ ] `grep -r "use_v2\|nav_data\|benchmark_data" src/` — only in a2a_adapter legacy comments if any
