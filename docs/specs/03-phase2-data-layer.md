# Phase 2 Data Layer Design

> 2026-06-19 | fortress v2.0 | brainstorm → design

## Scope

Build the complete data layer: ledger data model, SQLite persistence, market data source adapters with three-level fallback, and local cache.

**Out of scope**: Agent pipeline (Phase 4), redline rules (Phase 5), MCP tools (Phase 6), any UI.

---

## 1. Ledger — `src/engine/ledger.py`

GnuCash three-entity model as pure data classes. Zero I/O, zero dependencies.

### Types

```python
class AccountType(Enum):
    ASSET = "asset"           # 基金持仓、现金
    LIABILITY = "liability"   # 应付
    INCOME = "income"         # 收益
    EXPENSE = "expense"       # 费用
    EQUITY = "equity"         # 净资产

class Account(NamedTuple):
    path: str                 # "assets:funds:000001"
    type: AccountType
    commodity: str            # "CNY" | fund_code
    name: str                 # human-readable

class Transaction(NamedTuple):
    id: str                   # uuid
    date: date
    description: str
    splits: tuple[Split, ...] # ≥2 entries

class Split(NamedTuple):
    account_path: str
    amount: Decimal           # >0 = debit, <0 = credit
    memo: str = ""
```

### Validation (delayed constraint)

```python
@dataclass
class Violation:
    txn_id: str
    code: str                 # "unbalanced" | "missing_split" | "zero_amount"
    message: str

def validate_transaction(txn: Transaction) -> list[Violation]:
    """Check: has ≥2 splits, amounts sum to zero, no zero-amount splits."""
```

### Design decisions
- `tuple[Split, ...]` not `list[Split]` — Transaction is immutable once created
- Amount sign convention: debit=positive, credit=negative. Sum must equal zero.
- `account_path` as hierarchical string (`"assets:funds:000001"`) — same as GnuCash convention, supports tree navigation

---

## 2. Portfolio DB — `src/data/portfolio_db.py`

### Schema

```sql
CREATE TABLE accounts (
    path TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    commodity TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id TEXT NOT NULL REFERENCES transactions(id),
    account_path TEXT NOT NULL REFERENCES accounts(path),
    amount TEXT NOT NULL,     -- Decimal stored as string
    memo TEXT DEFAULT ''
);
```

### API

```python
class PortfolioDB:
    def __init__(self, db_path: str): ...
    # Account CRUD
    def create_account(self, acct: Account) -> None: ...
    def get_account(self, path: str) -> Account | None: ...
    def list_accounts(self, type: AccountType | None = None) -> list[Account]: ...
    # Transaction CRUD
    def create_transaction(self, txn: Transaction) -> None: ...
    def get_transaction(self, id: str) -> Transaction | None: ...
    def list_transactions(self, start: date, end: date) -> list[Transaction]: ...
    # Context manager for connection lifecycle
    def __enter__(self) -> PortfolioDB: ...
    def __exit__(self, ...) -> None: ...
```

### Design decisions
- `sqlite3` standard library (zero deps, synchronous, sufficient for single-user)
- Decimal amounts stored as TEXT (SQLite has no decimal type, FLOAT loses precision)
- `__enter__`/`__exit__` context manager — explicit connection lifecycle
- No ORM — raw SQL is readable and this schema is simple

---

## 3. Market Data — `src/data/market.py` + `src/data/sources/`

### Protocol

```python
class MarketDataSource(Protocol):
    name: str

    def fetch_fund_nav(self, code: str, start: date, end: date) -> list[NAVPoint]: ...
    def fetch_fund_info(self, code: str) -> FundInfo: ...
    def fetch_index_daily(self, code: str, start: date, end: date) -> list[IndexPoint]: ...

@dataclass
class NAVPoint:
    date: date
    nav: Decimal           # 单位净值
    acc_nav: Decimal       # 累计净值

@dataclass
class FundInfo:
    code: str
    name: str
    type: str              # "stock"|"bond"|"mixed"|"index"|"money"
    net_asset_value: Decimal  # 基金规模
    fee_rate: Decimal
    inception_date: date

@dataclass
class IndexPoint:
    date: date
    close: Decimal
    volume: Decimal
```

### Sources

| Source | Class | Data | Notes |
|--------|-------|------|-------|
| `akshare` | `AKShareSource` | 基金净值、基金信息、指数行情 | 主源 |
| 天天基金 | `TiantianSource` | 基金净值、基金信息 | 备源，直连无频率限制但需解析 HTML/JSONP |
| 东财 | `EastmoneySource` | 指数行情 | 备源 |

### Fallback facade

```python
class MarketDataFacade:
    def __init__(self, sources: list[MarketDataSource]): ...
    def fetch_fund_nav(self, code, start, end) -> list[NAVPoint]:
        """Try sources in order. On failure, try next. Raise if all fail."""
    def fetch_fund_info(self, code) -> FundInfo: ...
    def fetch_index_daily(self, code, start, end) -> list[IndexPoint]: ...
```

### Retry & rate-limit

```python
# Each source adapter handles its own retry
# AKShareSource: 3 retries with exponential backoff (1s/2s/4s), 2s interval between calls
# TiantianSource: 2 retries, 1s interval
# All sources: log failures, never crash
```

---

## 4. Cache — `src/data/cache.py`

### Schema (reuses portfolio_db pattern)

```sql
CREATE TABLE market_cache (
    key TEXT PRIMARY KEY,     -- "fund_nav:{code}:{start}:{end}" or "fund_info:{code}"
    data TEXT NOT NULL,       -- JSON serialized
    cached_at TEXT NOT NULL,  -- ISO timestamp
    ttl_seconds INTEGER NOT NULL
);
```

### API

```python
class MarketCache:
    def __init__(self, db_path: str): ...
    def get(self, key: str) -> str | None:   # returns JSON if valid, None if expired/missing
    def set(self, key: str, data: str, ttl_seconds: int) -> None: ...
    def invalidate(self, key_pattern: str) -> int:  # delete matching keys
```

### TTL strategy

| Data type | TTL |
|-----------|-----|
| 基金净值 (日频) | 24 hours |
| 基金信息 | 7 days |
| 指数行情 (日频) | 24 hours |

### Fallback integration

```python
# MarketDataFacade source chain:
#   [AKShareSource, TiantianSource, CachedSource(MarketCache)]
# CachedSource is always last — returns cached data if ≤TTL, otherwise passes through
class CachedSource(MarketDataSource):
    def __init__(self, cache: MarketCache): ...
    # On read: check cache, return if valid, otherwise raise (let caller handle)
```

---

## 5. Files Created

```
src/
├── __init__.py                    # (if not exists)
├── engine/
│   ├── __init__.py
│   └── ledger.py                  # Account, Transaction, Split, validate_transaction
├── data/
│   ├── __init__.py
│   ├── portfolio_db.py            # SQLite CRUD
│   ├── market.py                  # Protocol + MarketDataFacade + NAVPoint/FundInfo/IndexPoint
│   ├── cache.py                   # MarketCache
│   └── sources/
│       ├── __init__.py
│       ├── akshare.py             # AKShareSource
│       ├── tiantian.py            # TiantianSource
│       └── eastmoney.py           # EastmoneySource
tests/
├── engine/
│   └── test_ledger.py
├── data/
│   ├── test_portfolio_db.py
│   ├── test_market.py
│   └── test_cache.py
```

---

## 6. Dependencies Added

```toml
# pyproject.toml (new file)
[project]
name = "fortress"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "akshare>=1.16",
    "langgraph>=0.4",
    "riskfolio-lib>=7.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=6",
]
```

---

*Design doc v1.0 — ready for spec self-review.*
