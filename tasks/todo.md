# Phase 2 Task List

> 2026-06-19 | fortress v2.0

## Slice 1: Project Skeleton + Ledger

- [ ] **T1.1** `pyproject.toml` — project config, deps, dev-deps  
  _Verify_: `pip install -e .` succeeds
- [ ] **T1.2** `src/engine/ledger.py` — AccountType, Account, Transaction, Split, Violation, validate_transaction  
  _Verify_: `pytest tests/engine/test_ledger.py -v` all green
- [ ] **T1.3** `tests/engine/test_ledger.py` — balanced txn, unbalanced, <2 splits, zero amount, empty splits  
  _Verify_: 5+ parametrized cases

## Slice 2: Market Protocol

- [ ] **T2.1** `src/data/market.py` — MarketDataSource Protocol, NAVPoint, FundInfo, IndexPoint, MarketDataFacade  
  _Verify_: `MarketDataFacade` failover test with 2 mock sources
- [ ] **T2.2** `tests/data/test_market.py` — facade returns first success, skips failures, raises when all fail  
  _Verify_: 3 test cases

## Slice 3: Cache

- [ ] **T3.1** `src/data/cache.py` — MarketCache (schema, get/set/invalidate)  
  _Verify_: all cache operations via pytest
- [ ] **T3.2** `tests/data/test_cache.py` — set+get, miss, expiry, invalidate, overwrite  
  _Verify_: 5+ cases

## Slice 4: Data Sources

- [ ] **T4.1** `src/data/sources/akshare.py` — AKShareSource with retry  
  _Verify_: Protocol compliance, retry count, backoff timing
- [ ] **T4.2** `src/data/sources/tiantian.py` — TiantianSource  
  _Verify_: Protocol compliance
- [ ] **T4.3** `src/data/sources/eastmoney.py` — EastmoneySource  
  _Verify_: Protocol compliance

## Slice 5: CachedSource + Fallback Chain

- [ ] **T5.1** `src/data/market.py` — add CachedSource class  
  _Verify_: hit returns cached, miss raises
- [ ] **T5.2** `tests/data/test_market.py` — full chain: [AKShare❌ → Tiantian❌ → Cache✅], [AKShare✅ → returns immediately]  
  _Verify_: integration test with real cache DB + mock sources

## Slice 6: Portfolio DB

- [ ] **T6.1** `src/data/portfolio_db.py` — PortfolioDB with full CRUD + context manager  
  _Verify_: `pytest tests/data/test_portfolio_db.py -v` all green
- [ ] **T6.2** `tests/data/test_portfolio_db.py` — create/get/list account, create/get/list txn, unbalanced rejection, context manager  
  _Verify_: 8+ cases
- [ ] **T6.3** `scripts/init_db.py` — create empty DB with schema  
  _Verify_: `python scripts/init_db.py data/test.db && sqlite3 data/test.db ".tables"` shows accounts, transactions, splits

## Final Checkpoint

- [ ] `pytest tests/ -v --cov=src --cov-report=term` — all green, coverage ≥80% on engine/ and data/
