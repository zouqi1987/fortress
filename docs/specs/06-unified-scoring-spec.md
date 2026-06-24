# Spec: Unified Fund Scoring + NAV Storage Layer

## Objective

Fortress currently has a split scoring system: v1 (static-only, when NAV unavailable) and v2
(5-dimension, when caller passes `nav_data`). This split is fragile — most funds lack NAV because
the caller must fetch it per-fund, so v1 is the de-facto default and peer-relative evaluation is
impossible for the long tail.

This spec unifies scoring into a **single system** backed by a persistent NAV store, with
dimensions and weights **grounded in professional rating methodology** (Morningstar Medalist +
济安金信 6-dimension framework). Dimension weights adjust by **fund type** (active/passive/money)
and **investor risk profile** (conservative/moderate/aggressive).

**Methodology basis:**
- Morningstar Medalist (active): People 45% / Process 45% / Parent 10%, Price ~50% of net alpha
- Morningstar Medalist (passive): People 10% / Process 80% / Parent 10%
- 济安金信: 6 dimensions (盈利能力/抗风险/业绩稳定性/选股择时/基准跟踪/整体费用) × 3 levels
  (产品/公司/经理)
- Fortress's PoolFund already carries 4 agency ratings — these ARE the professional consensus on
  People/Process/Parent. We stand on their shoulders rather than reinventing qualitative judgment.

**User stories:**
- As an investor screening funds, I want every fund scored on the same dimensions regardless of
  fund type — active funds weighed on manager/consensus, passive on fee/tracking.
- As an investor, I want peer-relative performance to affect the score, not just be a display field.
- As a conservative investor, I want risk control and fee weighted higher than raw performance;
  an aggressive investor wants the opposite.
- As an investor in a **finance project with zero tolerance for error**, I want funds with
  insufficient data **excluded** — never assigned a fabricated "neutral" score.

**Success looks like:** `screen_funds` returns one score per fund on a 0–100 scale, computed from
5 weighted dimensions, with weights varying by fund type × risk profile. No v1/v2 branch. Funds
with missing required data are excluded with a clear reason — never given a fake score.

## Tech Stack

Pure Python, extending existing fortress modules. **No new dependencies.**

- akshare (existing) — NAV fetch (`fund_open_fund_info_em` per-fund, `fund_open_fund_daily_em` bulk)
- SQLite (existing `MarketCache` in `src/data/cache.py`) — NAV time-series storage
- scipy (existing) — unchanged (portfolio optimization, not scoring)
- Jinja2 (existing) — report template updates

## Commands

```
Backfill NAV (one-time):   python3 -m src.data.sources.nav_store --backfill
Daily incremental:         python3 -m src.data.sources.nav_store --update
Gap recovery (auto):       python3 -m src.data.sources.nav_store --update --recover
Inspect store:             python3 -m src.data.sources.nav_store --stats

Test scoring engine:       python3 -m pytest tests/engine/test_unified_screener.py -v
Test NAV store:            python3 -m pytest tests/data/test_nav_store.py -v
Test peer scoring:         python3 -m pytest tests/engine/test_peer_scoring.py -v
All tests:                 python3 -m pytest tests/
```

## Project Structure

```
src/
├── data/
│   ├── sources/
│   │   ├── nav_store.py          ← NEW: NAV time-series storage + backfill/update/recover
│   │   └── fund_pool.py          ← existing (no change; PoolFund already has 4 ratings)
│   └── cache.py                  ← existing MarketCache, reused for NAV table
├── engine/
│   ├── screener.py               ← REWRITE: unified score_funds(), remove v1/v2 branch
│   ├── peer_scoring.py           ← NEW: peer-relative scoring from PoolFund 5-period excess
│   ├── institutional_consensus.py ← NEW: composite score from 4 agency ratings
│   └── risk_personalization.py   ← NEW: weight tables by fund-type × risk-profile
├── tools/
│   └── screener.py               ← MODIFY: drop nav_data param, read from nav_store
└── report/
    ├── context.py                ← MODIFY: pass 5-dimension breakdown to template
    └── templates/report.html     ← MODIFY: show dimension breakdown + active weights
tests/
├── data/
│   └── test_nav_store.py         ← NEW
├── engine/
│   ├── test_unified_screener.py  ← NEW (replaces test_screener.py + test_screener_v2.py)
│   ├── test_peer_scoring.py      ← NEW
│   ├── test_institutional_consensus.py ← NEW
│   └── test_risk_personalization.py ← NEW
```

## Code Style

Follow existing fortress conventions strictly:

```python
# engine/ layer: zero I/O, pure functions, Decimal for amounts
def score_peer_performance(
    fund_returns: dict[str, float],      # {"ret_1m": 1.2, "ret_3m": 3.1, ...}
    category_averages: dict[str, float], # same shape, peer mean
    weights: dict[str, float],           # per-period weights, sum=1
) -> int:
    """Score peer-relative performance 0-100. 50 = peer average."""
    excess = {p: fund_returns[p] - category_averages.get(p, 0.0) for p in fund_returns}
    weighted_excess = sum(excess[p] * weights[p] for p in excess)
    return int(max(0, min(100, 50 + weighted_excess * 2)))
```

- `engine/` = zero I/O pure functions; all data passed in as args
- `decimal.Decimal` for all money/fee amounts; `float` ok for returns/ratios
- Type hints on all public functions
- No mutating args; return new structures
- Raise `InsufficientDataError` when required data missing — caller excludes, never fabricates

## Testing Strategy

**Framework:** pytest (existing). **TDD:** failing test first, then implement (per
`test-driven-development` skill).

**Test levels:**
- **Unit (engine/):** pure-function tests with synthetic inputs. Cover: all 5 dimensions, 9 weight
  combinations (3 fund types × 3 risk profiles), exclusion on missing data, edge cases.
- **Unit (data/):** `test_nav_store.py` with temp SQLite DB. Cover: backfill append idempotency,
  daily incremental dedup, gap detection, recovery tiers, trading-day awareness.
- **Integration:** `screen_funds` end-to-end with seeded nav_store + fund pool subset.
- **Regression:** existing `test_category_benchmark.py` + `test_fund_pool.py` must still pass.

**Coverage expectations:** every new public function has ≥3 test cases (happy path, edge, error).
Existing 304 test functions must not regress.

**Baselines:** `tests/engine/test_screener.py` + `test_screener_v2.py` are replaced by
`test_unified_screener.py`; their assertions are ported (not deleted) as same-behavior checks
where the behavior is preserved.

## Design

### 1. NAV Storage Layer (`src/data/sources/nav_store.py`)

**Schema** (new table in existing `market_cache.db`):

```sql
CREATE TABLE IF NOT EXISTS fund_nav (
    code        TEXT NOT NULL,
    nav_date    TEXT NOT NULL,       -- ISO 'YYYY-MM-DD'
    unit_nav    REAL NOT NULL,       -- 单位净值
    accum_nav   REAL,                -- 累计净值 (nullable for funds without it)
    PRIMARY KEY (code, nav_date)
);
CREATE INDEX IF NOT EXISTS idx_fund_nav_code ON fund_nav(code);
CREATE INDEX IF NOT EXISTS idx_fund_nav_date ON fund_nav(nav_date);

CREATE TABLE IF NOT EXISTS nav_backfill_progress (
    code        TEXT PRIMARY KEY,
    status      TEXT NOT NULL,       -- 'pending' | 'done' | 'failed'
    fetched_at  TEXT,
    point_count INTEGER
);
```

**`NavStore` class:**
- `backfill(codes: list[str], period: str = "3年") -> BackfillReport`
  - Per-fund `ak.fund_open_fund_info_em(symbol=code, period=period)`, concurrent (max 20 workers)
  - Idempotent: `INSERT OR IGNORE` on (code, nav_date)
  - Resumable: tracks progress in `nav_backfill_progress`; skipped codes on restart
  - **Full market scope**: all 19,747 pool funds (no subset — finance project tolerates no gaps)
  - Reports: fetched / skipped / failed counts
- `update() -> UpdateReport`
  - Detect gap: `SELECT MAX(nav_date) FROM fund_nav` vs today's trading date
  - gap ≤ 2 trading days: `ak.fund_open_fund_daily_em()` → bulk append (1 HTTP)
  - gap 3-30 trading days: lazy-recover holdings + active-query funds first (per-fund
    `period="1月"`), then background-recover remainder
  - gap > 30: log warning, defer to manual `backfill`
- `get_nav_series(code: str, days: int = 750) -> list[float]`
  - Returns daily unit_nav for the last N trading days, oldest-first
- `coverage_report() -> CoverageReport`
  - Returns: total pool funds, funds with NAV, funds missing NAV, latest date
  - Used by `screen_funds` to refuse if store is empty
- `stats() -> dict` — fund count, date range, per-fund point counts

**Trading-day awareness:** use `ak.tool_trade_date_hist_sina()` (cached) to distinguish trading vs
calendar days — NAV only updates on trading days, so weekend gaps are not real gaps.

**Completeness gate:** `screen_funds` calls `nav_store.coverage_report()` at entry. If store is
empty (0% coverage), refuse with instructions to backfill. If store has data but some funds
missing NAV, those funds are **excluded** (not fabricated) with a warning.

### 2. Unified Scoring (`src/engine/screener.py` — rewrite)

**Single function, no v1/v2 branch:**

```python
def score_funds(
    funds: list[FundInfo],
    config: ScreenConfig,
    nav_store: NavStore,
    pool_index: dict[str, PoolFund],
    category_averages: dict[str, dict[str, float]],
    risk_level: str = "moderate",
) -> list[ScreenResult]:
```

**Five scoring dimensions (0-100 each, then weighted to final 0-100):**

| Dimension | Source | What it measures | Morningstar analog | 济安金信 analog |
|-----------|--------|------------------|--------------------|-----------------|
| Institutional consensus | 4 agency ratings in PoolFund | People+Process+Parent composite | People+Process+Parent (90% active) | 产品+公司+经理 |
| Peer performance | PoolFund 5-period excess vs category avg | Returns vs peers | Performance (validation) | 盈利能力 |
| Risk control | Stored NAV: volatility + max drawdown | Downside risk | (in Process) | 抗风险能力 |
| Persistence | Stored NAV: return stability | Performance consistency | (in Process) | 业绩稳定性 |
| Fee | PoolFund.fee | Cost drag | Price (~50% net alpha) | 整体费用 |

**Money funds** (`fund_type == "money"`): only 3 dimensions apply (consensus + performance + fee).
Risk control and persistence are **structurally N/A** (摊余成本法, no volatility) — this is by
design, not missing data. Weights redistribute across the 3 applicable dimensions.

**Exclusion rules (no fabricated data — finance project principle):**
- All 4 agency ratings = 0 → exclude, warning: `"无机构评级，无法评估，已排除"`
- NAV points < 63 → exclude, warning: `"NAV 数据不足(<63 点)，无法评估风控/持续性，已排除"`
- Fund age < 1 year → still scored, warning: `"成立不足 1 年，评分置信度低"`
- nav_store empty → `screen_funds` refuses entirely, instructs user to backfill

**Final score:**

```python
fund_type_class = _classify_fund_type(fund.fund_type)  # "active" | "passive" | "money"
weights = WEIGHTS[fund_type_class][risk_level]
final = sum(dimension_score[dim] * weights[dim] for dim in weights)
```

### 3. Institutional Consensus (`src/engine/institutional_consensus.py` — new, zero I/O)

```python
def score_institutional_consensus(
    ratings: dict[str, float],  # {"morningstar": 4, "shanghai": 3, "zhaoshang": 0, "jiAn": 5}
) -> int:
    """0-100 from agency ratings. Raises InsufficientDataError if all ratings are 0."""
    valid = {k: v for k, v in ratings.items() if v > 0}
    if not valid:
        raise InsufficientDataError("无机构评级")
    avg = sum(valid.values()) / len(valid)  # 0-5
    return int(avg * 20)  # 0-100
```

- Only counts non-zero ratings (0 = unrated by that agency)
- If ALL 4 are 0 → raise → caller excludes the fund
- This dimension is available immediately from PoolFund (no NAV needed)

### 4. Peer Scoring (`src/engine/peer_scoring.py` — new, zero I/O)

```python
PERIOD_WEIGHTS = {  # weight each period when aggregating peer excess
    "ret_1m": 0.10, "ret_3m": 0.15, "ret_6m": 0.20,
    "ret_1y": 0.35, "ret_3y": 0.20,
}

def score_peer_performance(
    fund_returns: dict[str, float],
    category_averages: dict[str, float],
    period_weights: dict[str, float] = PERIOD_WEIGHTS,
) -> int:
    """0-100. 50 = peer-average; >50 beats peers; <50 lags."""
```

- Computes weighted excess across 5 periods
- Maps to 0-100 with 50 as the neutral midpoint (linear, clamped)
- Uses `compute_category_averages` output (existing) — prefers `raw_type` granularity, falls back
  to broad category

### 5. Risk Personalization (`src/engine/risk_personalization.py` — new)

Weight tables by **fund type × investor risk profile**. Each row sums to 1.0.

**Active funds (bond/mixed/stock):**

| Dimension | Conservative | Moderate | Aggressive |
|-----------|:---:|:---:|:---:|
| Institutional consensus | 0.25 | 0.25 | 0.20 |
| Peer performance | 0.10 | 0.25 | 0.40 |
| Risk control | 0.30 | 0.20 | 0.10 |
| Persistence | 0.15 | 0.10 | 0.10 |
| Fee | 0.20 | 0.20 | 0.20 |

**Passive funds (index):**

| Dimension | Conservative | Moderate | Aggressive |
|-----------|:---:|:---:|:---:|
| Institutional consensus | 0.20 | 0.15 | 0.10 |
| Peer performance (tracking) | 0.15 | 0.20 | 0.25 |
| Risk control | 0.15 | 0.10 | 0.05 |
| Persistence | 0.10 | 0.10 | 0.10 |
| Fee | 0.40 | 0.45 | 0.50 |

Rationale: passive funds are commoditized — fee is the primary differentiator (Morningstar
passive methodology: Process 80%, fee paramount). Manager/consensus matters little.

**Money funds:**

| Dimension | Conservative | Moderate | Aggressive |
|-----------|:---:|:---:|:---:|
| Institutional consensus | 0.40 | 0.35 | 0.30 |
| Peer performance (yield) | 0.30 | 0.35 | 0.40 |
| Fee | 0.30 | 0.30 | 0.30 |

Rationale: money funds have no volatility (摊余成本法) — risk/persistence structurally N/A.
Safety (consensus) matters most for conservative; yield matters most for aggressive.

### 6. Tool Layer (`src/tools/screener.py` — modify)

- Drop `nav_data` parameter (caller no longer fetches NAV)
- Drop `benchmark_data` parameter (relative scoring now via peer dimension)
- `screen_funds` reads from `NavStore` (singleton, module-level) + fund pool
- `peer_comparison` output field **kept** for display, now reflects scoring input
- Calls `nav_store.coverage_report()` at entry; refuses if store empty

### 7. Report (`src/report/` — modify)

- `context.py` passes 5-dimension breakdown + active weight table to template
- `report.html` §7.5 expands to show per-fund dimension scores + active weights, with the fund
  type class labeled (主动/被动/货币)

## Boundaries

- **Always do:**
  - engine/ layer stays zero I/O — `NavStore` lives in `data/`, scoring functions receive
    pre-fetched series
  - All amounts `Decimal`; returns/ratios `float`
  - Run full test suite before commit; never regress existing 304 tests
  - NAV fetch uses `INSERT OR IGNORE` (idempotent); never overwrite historical points
  - Backfill is resumable — never restart from scratch on interruption
  - **Exclude funds with insufficient data — never fabricate a "neutral" score** (finance principle)
  - **Backfill all 19,747 pool funds — no subset** (no missing data tolerated)
- **Ask first:**
  - Changing the weight tables (these encode investment philosophy, grounded in Morningstar/济安金信)
  - Adding new akshare endpoints beyond the 3 verified (`fund_open_fund_info_em`,
    `fund_open_fund_daily_em`, `fund_open_fund_rank_em`)
  - Changing fund type classification granularity
  - Backfill concurrency > 20 (akshare rate-limit risk)
- **Never do:**
  - Mutate historical NAV points once stored (past is immutable)
  - Fabricate data for missing dimensions (no "neutral 50" — exclude instead)
  - Auto-trade or recommend individual stocks
  - Hardcode fund data — all data from live API / stored cache
  - Mix I/O into engine/ functions
  - Delete `test_screener.py` / `test_screener_v2.py` assertions without porting them

## Success Criteria

- [ ] `screen_funds` has no `nav_data` parameter; no v1/v2 branch in `engine/screener.py`
- [ ] Every scored fund gets a single 0-100 score from 5 weighted dimensions (3 for money funds)
- [ ] Manager/consensus is a top-level dimension (not folded into static) — per Morningstar 45%
- [ ] Weights vary by fund type (active/passive/money) AND risk profile — 9 combinations total
- [ ] Institutional consensus dimension uses 4 agency ratings; all-zero → fund excluded
- [ ] Peer dimension uses PoolFund 5-period excess vs `compute_category_averages` output
- [ ] NAV < 63 points → fund **excluded** with warning (not neutral 50, not zero)
- [ ] `nav_store` empty → `screen_funds` refuses, instructs backfill
- [ ] `NavStore.backfill` is idempotent + resumable; covers all 19,747 pool funds
- [ ] `NavStore.update` detects gap correctly (trading-day aware); ≤2-day gap = 1 bulk HTTP
- [ ] Gap recovery: 3-30 day gap lazy-recovers queried funds, background-recovers rest
- [ ] Report §7.5 shows 5-dimension breakdown with active weights + fund type class
- [ ] All existing 304 tests pass (ported where behavior preserved)
- [ ] New modules have ≥3 test cases per public function

## Open Questions

1. **Tushare optimization**: `fund_nav` API (2000 points) may support `trade_date` bulk query
   (~1500 calls vs 19,747 for backfill). Unverified — docs behind login. Deferred to post-spec;
   current spec uses akshare per-fund (verified). If Tushare pans out later, only
   `nav_store.backfill` internals change — scoring layer unaffected.

2. **Profit probability as persistence**: `fund_individual_profit_probability_xq` gives a direct
   "persistence" metric (盈利概率). Current spec computes consistency from NAV series. Could later
   switch persistence dimension to use the akshare profit-probability API per-fund — but that
   reintroduces per-fund HTTP at query time. Deferred.

3. **PoolFund period expansion**: `fund_open_fund_rank_em` returns 9 periods (1w/1m/3m/6m/1y/2y/
   3y/YTD/since-inception) but `PoolFund` only stores 5. Spec uses existing 5. Expanding to 9 is
   a separate data-model change — ask-first per spec 04 boundaries.

4. **Selection/timing ability (选股择时)**: 济安金信 evaluates this for active funds. Fortress does
   not (retail tool, no holdings data for stock-picking attribution). Could add later via
   `fund_portfolio_hold_em` (holdings data). Deferred — current 5 dimensions cover the core.
