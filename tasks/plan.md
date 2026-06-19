# Phase 2 Implementation Plan

> 2026-06-19 | fortress v2.0 | vertical slices

## Dependency Graph

```
pyproject.toml ─────────────────────────────────────────────┐
                                                            │
src/engine/ledger.py (pure data) ───┐                       │
                                     │                      │
src/data/market.py (protocol+dto) ───┤                      │
                                     │                      │
src/data/cache.py (sqlite3) ────────┐│                      │
                                    ││                      │
src/data/sources/akshare.py ────────┤│                      │
src/data/sources/tiantian.py ──────┤│                      │
src/data/sources/eastmoney.py ─────┤│                      │
                                    ││                      │
src/data/market.py (facade) ────────┘│                      │
                                     │                      │
src/data/portfolio_db.py ────────────┘                      │
                                                            │
tests/  ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ┘
```

## Vertical Slices

### Slice 1: Project Skeleton + Ledger Data Model
**Files**: `pyproject.toml`, `src/__init__.py`, `src/engine/__init__.py`, `src/engine/ledger.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/engine/__init__.py`, `tests/engine/test_ledger.py`

**Acceptance Criteria**:
- [ ] `pyproject.toml` installs with `pip install -e .`
- [ ] `Account`, `Transaction`, `Split` types importable
- [ ] `validate_transaction()` catches: unbalanced, <2 splits, zero-amount splits
- [ ] Valid transaction passes validation (empty list returned)
- [ ] All tests pass: `pytest tests/engine/test_ledger.py -v`

### Slice 2: Market Protocol + Data Types
**Files**: `src/data/__init__.py`, `src/data/market.py`, `tests/data/__init__.py`, `tests/data/test_market.py`

**Acceptance Criteria**:
- [ ] `MarketDataSource` Protocol defined
- [ ] `NAVPoint`, `FundInfo`, `IndexPoint` dataclasses importable
- [ ] `MarketDataFacade` failover logic works (mock sources)
- [ ] Facade raises when all sources fail
- [ ] Facade returns first successful source's data

### Slice 3: Cache Layer
**Files**: `src/data/cache.py`, `tests/data/test_cache.py`

**Acceptance Criteria**:
- [ ] `MarketCache` creates table on init
- [ ] `get()` returns None for missing key
- [ ] `get()` returns data for valid (non-expired) key
- [ ] `get()` returns None for expired key
- [ ] `set()` stores data with TTL
- [ ] `invalidate()` deletes matching keys, returns count

### Slice 4: Data Source Adapters
**Files**: `src/data/sources/__init__.py`, `src/data/sources/akshare.py`, `src/data/sources/tiantian.py`, `src/data/sources/eastmoney.py`, `tests/data/sources/__init__.py`

**Acceptance Criteria**:
- [ ] All three sources implement `MarketDataSource` Protocol
- [ ] `AKShareSource` retry logic: 3 attempts, exponential backoff
- [ ] `TiantianSource` retry logic: 2 attempts
- [ ] Each source has `name` attribute
- [ ] Sources don't crash on network errors (log + raise after retries exhaust)

### Slice 5: CachedSource + Full Fallback Chain
**Files**: Update `src/data/market.py` (add `CachedSource`), `tests/data/test_market.py` (integration tests)

**Acceptance Criteria**:
- [ ] `CachedSource` implements `MarketDataSource` Protocol
- [ ] `CachedSource` returns cached data when valid
- [ ] `CachedSource` raises when cache miss
- [ ] Full chain `[AKShare, Tiantian, CachedSource]` falls through correctly
- [ ] Integration test with real cache + mock sources

### Slice 6: Portfolio DB
**Files**: `src/data/portfolio_db.py`, `tests/data/test_portfolio_db.py`, `scripts/init_db.py`

**Acceptance Criteria**:
- [ ] `PortfolioDB` creates schema on init
- [ ] Account CRUD: create, get (by path), list (all, by type)
- [ ] Transaction CRUD: create (with splits), get (with splits), list (by date range)
- [ ] Creating unbalanced transaction raises ValueError
- [ ] Context manager opens/closes connection
- [ ] `scripts/init_db.py` creates empty DB

## Checkpoints

| After Slice | Check |
|-------------|-------|
| 1 | `pytest tests/ -v` — all existing tests green |
| 2 | Facade failover with 3 mock sources passes |
| 3 | Cache TTL expiry verified |
| 4 | All adapters importable, Protocol compliance verified by mypy |
| 5 | Full chain fallback integration test passes |
| 6 | All 6 test files pass, `pytest --cov=src` shows coverage |

## Out of Scope
- LangGraph agent pipeline (Phase 4)
- Redline rules (Phase 5)
- MCP tool registration (Phase 6)
- Real API integration tests (CI-safe — marked `@pytest.mark.integration`)
