# Implementation Plan: Unified Fund Scoring + NAV Storage Layer

Reference spec: `docs/specs/06-unified-scoring-spec.md`

## Architecture Decisions

- **Bottom-up implementation**: engine pure functions first (testable in isolation, no I/O), then
  data layer (NAV store), then the unified screener that wires them together, then tool/report.
- **Port, don't delete**: assertions from `test_screener.py` + `test_screener_v2.py` are ported to
  `test_unified_screener.py` where behavior is preserved. This guards against regression.
- **Weights in a standalone module** (`risk_personalization.py`): the 9 weight tables are the
  investment-philosophy core — isolating them makes future tuning a one-file change.
- **NAV store is the long pole**: backfill of 19,747 funds is the only step that can't be
  unit-tested in isolation (needs real network). Everything else is pure functions + temp SQLite.

## Component Dependency Graph

```
Phase 1 (parallel, pure functions, zero I/O):
  ┌─ institutional_consensus.py ���─┐
  ├─ peer_scoring.py ─────────────┼── no dependencies on each other
  └─ risk_personalization.py ─────┘

Phase 2 (independent of Phase 1):
  └─ nav_store.py ──── depends on: akshare, existing MarketCache

Phase 3 (depends on Phase 1 + 2):
  └─ screener.py (rewrite) ──── depends on: all Phase 1 modules + nav_store + category_benchmark

Phase 4 (depends on Phase 3):
  ├─ tools/screener.py (modify) ── depends on: unified screener + nav_store singleton
  └─ report/ (modify) ─────────── depends on: unified screener output shape
```

## Implementation Order

### Phase 1: Engine Pure Functions (parallel, TDD)

Three independent modules, zero I/O, each testable immediately. Can be built in parallel.

- [ ] **1a**: `src/engine/institutional_consensus.py` + `tests/engine/test_institutional_consensus.py`
- [ ] **1b**: `src/engine/peer_scoring.py` + `tests/engine/test_peer_scoring.py`
- [ ] **1c**: `src/engine/risk_personalization.py` + `tests/engine/test_risk_personalization.py`

**Checkpoint 1**: All 3 modules' tests pass. Existing 304 tests still pass. No I/O introduced.

### Phase 2: NAV Storage Layer

- [ ] **2a**: `src/data/sources/nav_store.py` — schema, `NavStore` class, `get_nav_series`,
  `coverage_report`, `stats`
- [ ] **2b**: `backfill()` — concurrent per-fund fetch, idempotent INSERT OR IGNORE, resumable
  progress tracking
- [ ] **2c**: `update()` — gap detection (trading-day aware), tiered recovery (≤2 days bulk,
  3-30 lazy+background, >30 defer)
- [ ] **2d**: `tests/data/test_nav_store.py` — temp SQLite, idempotency, dedup, gap detection,
  recovery tiers

**Checkpoint 2**: nav_store unit tests pass (with mocked akshare). Small live backfill of 10 funds
works end-to-end. Full 19,747 backfill can run but is NOT required to proceed (Phase 3 tests use
seeded data).

### Phase 3: Unified Screener (rewrite)

- [ ] **3a**: `src/engine/screener.py` — `score_funds()` signature, fund-type classification
  (`_classify_fund_type` → active/passive/money), exclusion logic (InsufficientDataError handling)
- [ ] **3b**: Wire 5 dimensions: institutional_consensus + peer_scoring + existing
  score_risk_control/score_consistency (refactored to read from nav_store series) + fee scoring
- [ ] **3c**: Apply risk_personalization weights (fund-type × risk-profile lookup)
- [ ] **3d**: `tests/engine/test_unified_screener.py` — port assertions from test_screener.py +
  test_screener_v2.py; add new tests for 9 weight combinations, exclusion rules, money fund path

**Checkpoint 3**: Unified screener tests pass. No v1/v2 branch remains. `grep "use_v2\|v1.*static"
src/engine/screener.py` returns nothing. Existing category_benchmark tests still pass.

### Phase 4: Tool Layer + Report

- [ ] **4a**: `src/tools/screener.py` — drop `nav_data`/`benchmark_data` params, read from
  NavStore singleton, add coverage gate (refuse if store empty)
- [ ] **4b**: `src/report/context.py` — pass 5-dimension breakdown + active weight table
- [ ] **4c**: `src/report/templates/report.html` — §7.5 expand to dimension breakdown + fund type
  label + active weights
- [ ] **4d**: Integration test — `screen_funds` end-to-end with seeded nav_store + pool subset

**Checkpoint 4**: End-to-end works. Report renders dimension breakdown. Full test suite green.

## Parallelization Opportunities

- **Phase 1 (1a/1b/1c)**: fully parallel — 3 independent pure-function modules.
- **Phase 2** can start in parallel with Phase 1 (no dependency).
- **Phase 3** is sequential after 1 + 2.
- **Phase 4a (tool) and 4b/4c (report)** can parallelize after 3.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Full 19,747 backfill is slow / rate-limited | Medium | Resumable progress table; 20-worker concurrency cap; NOT required for Phase 3 (tests use seeded data) |
| Existing screener tests regress on rewrite | High | Port assertions to test_unified_screener.py BEFORE deleting old tests; run full suite after Phase 3 |
| NAV data quality varies (sparse for new/odd funds) | Medium | Exclusion rules (< 63 points → exclude with warning); never fabricate |
| Weight tables need tuning after real-data testing | Low | Weights isolated in risk_personalization.py — one-file change |
| akshare API changes/breaks | Medium | All akshare calls isolated in data/sources/ layer; engine stays pure |
| Trading-day detection edge cases (holidays) | Low | Use akshare's trade_date_hist_sina (authoritative); cache locally |

## Verification Checkpoints

| Checkpoint | After | Gate condition |
|---|---|---|
| CP1 | Phase 1 | 3 new engine modules' tests pass; 304 existing pass; zero I/O in engine/ |
| CP2 | Phase 2 | nav_store tests pass; 10-fund live backfill works; gap detection correct |
| CP3 | Phase 3 | Unified screener tests pass; no v1/v2 branch; category_benchmark tests pass |
| CP4 | Phase 4 | End-to-end screen_funds works; report renders; full suite green |

## What is NOT in this plan

- Full 19,747 backfill execution (runtime task, not implementation; can run after CP2)
- Tushare integration (Open Question — deferred)
- Profit-probability API for persistence (Open Question — deferred)
- PoolFund 9-period expansion (Open Question — deferred)
- Selection/timing ability (Open Question — deferred)
