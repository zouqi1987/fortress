# discover_funds Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 17th MCP tool `discover_funds` that filters/ranks the full 19,747-fund pool via two-stage scoring, returning top N funds — eliminating the web-search bias in candidate selection.

**Architecture:** Stage 1 light-scores all pool funds on 3 NavStore-free dims (consensus/peer/fee) → top 200. Stage 2 enriches those 200 with 2 NavStore-dependent dims (risk_control/persistence) and recomputes with full 5-dim weights → top_n. New engine function `score_funds_light` (pure, no I/O) + new tool `discover_funds` in `src/tools/discover.py`.

**Tech Stack:** Python 3, FastMCP, pytest, decimal.Decimal, existing Fortress engine (score_institutional_consensus, score_peer_performance, _score_fee, score_risk_control, score_consistency, get_weights, classify_fund_type).

**Spec:** `docs/specs/09-discover-funds-spec.md`

---

## Task 1: Stage 1 weight helper — `get_weights_light`

**Files:**
- Modify: `src/engine/risk_personalization.py` (add function after `get_weights`, ~line 161)
- Test: `tests/engine/test_risk_personalization.py` (add tests)

**Step 1: Write failing tests**

Append to `tests/engine/test_risk_personalization.py`:

```python
import pytest
from src.engine.risk_personalization import get_weights_light, get_weights


class TestGetWeightsLight:
    def test_active_conservative_renormalized(self):
        w = get_weights_light("active", "conservative")
        assert set(w.keys()) == {"institutional_consensus", "peer_performance", "fee"}
        assert abs(sum(w.values()) - 1.0) < 1e-9
        # 0.25/0.55, 0.10/0.55, 0.20/0.55
        assert abs(w["institutional_consensus"] - 0.4545) < 0.001
        assert abs(w["peer_performance"] - 0.1818) < 0.001
        assert abs(w["fee"] - 0.3636) < 0.001

    def test_money_unchanged(self):
        """Money funds already 3-dim — Stage 1 weights == full weights."""
        full = get_weights("money", "conservative")
        light = get_weights_light("money", "conservative")
        assert set(light.keys()) == set(full.keys())
        for k in full:
            assert abs(light[k] - full[k]) < 1e-9

    def test_passive_aggressive_fee_dominant(self):
        w = get_weights_light("passive", "aggressive")
        assert w["fee"] > 0.50  # fee should dominate
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_invalid_class_raises(self):
        with pytest.raises(ValueError, match="未知基金类型类"):
            get_weights_light("hedge_fund", "conservative")

    def test_all_9_combinations_sum_to_one(self):
        for cls in ("active", "passive", "money"):
            for risk in ("conservative", "moderate", "aggressive"):
                w = get_weights_light(cls, risk)
                assert abs(sum(w.values()) - 1.0) < 1e-9, f"{cls}/{risk} doesn't sum to 1"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/engine/test_risk_personalization.py::TestGetWeightsLight -v
```
Expected: FAIL with `ImportError: cannot import name 'get_weights_light'`

**Step 3: Implement `get_weights_light`**

Append to `src/engine/risk_personalization.py`:

```python
_STAGE1_DIMS = ("institutional_consensus", "peer_performance", "fee")


def get_weights_light(fund_type_class: str, risk_level: str) -> dict[str, float]:
    """Stage 1 weights — 3 NavStore-free dims, renormalized to sum 1.0.

    For money funds: identical to get_weights (already 3-dim, no loss).
    For active/passive: drops risk_control + persistence, renormalizes
    the remaining 3 dims (consensus/peer/fee) to sum to 1.0.

    Used by score_funds_light to pre-rank the full pool without NavStore.

    Args:
        fund_type_class: "active", "passive", or "money".
        risk_level:      "conservative", "moderate", or "aggressive".

    Returns:
        Dict of 3 dimension weights summing to 1.0.

    Raises:
        ValueError: If fund_type_class or risk_level is invalid.
    """
    full = get_weights(fund_type_class, risk_level)  # raises ValueError if invalid
    available = {k: v for k, v in full.items() if k in _STAGE1_DIMS}
    total = sum(available.values())
    if total == 0:
        raise ValueError(
            f"Stage 1 dimensions all zero for {fund_type_class}/{risk_level}"
        )
    return {k: v / total for k, v in available.items()}
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/engine/test_risk_personalization.py::TestGetWeightsLight -v
```
Expected: 5 passed

**Step 5: Commit**

```bash
git add src/engine/risk_personalization.py tests/engine/test_risk_personalization.py
git commit -m "feat: add get_weights_light for Stage 1 renormalized weights"
```

---

## Task 2: Stage 1 scoring — `score_funds_light`

**Files:**
- Modify: `src/engine/screener.py` (add `score_funds_light` + `LightResult` dataclass)
- Test: `tests/engine/test_screener_light.py` (new file)

**Step 1: Write failing tests**

Create `tests/engine/test_screener_light.py`:

```python
"""Tests for score_funds_light — Stage 1 scoring (3 dims, no NavStore)."""
import pytest
from decimal import Decimal
from src.engine.screener import score_funds_light, LightResult, ScreenConfig
from src.data.sources.fund_pool import PoolFund


def _make_pool_fund(
    code="000001", name="Test Fund", fund_type="bond", raw_type="债券型-纯债",
    manager="张三", fee=Decimal("0.015"),
    ret_1y=5.0, ret_3y=15.0, ret_1m=0.5, ret_3m=1.5, ret_6m=3.0,
    morningstar=4, shanghai=4, zhaoshang=4, jiAn=4,
):
    return PoolFund(
        code=code, name=name, fund_type=fund_type, raw_type=raw_type,
        manager=manager, fee=fee,
        ret_1m=ret_1m, ret_3m=ret_3m, ret_6m=ret_6m, ret_1y=ret_1y, ret_3y=ret_3y,
        rating_morningstar=morningstar, rating_shanghai=shanghai,
        rating_zhaoshang=zhaoshang, rating_jiAn=jiAn,
    )


CATEGORY_AVERAGES = {
    "bond": {"ret_1m": 0.19, "ret_3m": 1.41, "ret_6m": 2.04, "ret_1y": 4.19, "ret_3y": 11.18},
}


class TestScoreFundsLight:
    def test_scores_single_fund_returns_one_result(self):
        pool = [_make_pool_fund()]
        config = ScreenConfig()
        results = score_funds_light(pool, config, CATEGORY_AVERAGES, "conservative")
        assert len(results) == 1
        assert results[0].code == "000001"
        assert 0 <= results[0].score <= 100

    def test_excludes_fund_with_all_zero_ratings(self):
        pool = [_make_pool_fund(morningstar=0, shanghai=0, zhaoshang=0, jiAn=0)]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        assert len(results) == 0  # excluded — no ratings

    def test_excludes_fund_with_no_category_averages(self):
        pool = [_make_pool_fund(fund_type="exotic_type")]
        empty_avgs = {}
        results = score_funds_light(pool, ScreenConfig(), empty_avgs, "conservative")
        assert len(results) == 0

    def test_filters_by_allowed_types(self):
        pool = [_make_pool_fund(code="A", fund_type="bond"),
                _make_pool_fund(code="B", fund_type="mixed")]
        config = ScreenConfig(allowed_types=frozenset({"bond"}))
        results = score_funds_light(pool, config, CATEGORY_AVERAGES, "conservative")
        assert len(results) == 1
        assert results[0].code == "A"

    def test_filters_by_max_fee_rate(self):
        pool = [_make_pool_fund(code="A", fee=Decimal("0.010")),
                _make_pool_fund(code="B", fee=Decimal("0.020"))]
        config = ScreenConfig(max_fee_rate=Decimal("0.015"))
        results = score_funds_light(pool, config, CATEGORY_AVERAGES, "conservative")
        assert len(results) == 1
        assert results[0].code == "A"

    def test_higher_rated_fund_scores_higher(self):
        pool = [_make_pool_fund(code="low", morningstar=2, shanghai=2, zhaoshang=2, jiAn=2),
                _make_pool_fund(code="high", morningstar=5, shanghai=5, zhaoshang=5, jiAn=5)]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        assert results[0].code == "high"  # sorted desc
        assert results[0].score > results[1].score

    def test_results_sorted_by_score_descending(self):
        pool = [_make_pool_fund(code="low", morningstar=2, shanghai=2, zhaoshang=2, jiAn=2),
                _make_pool_fund(code="high", morningstar=5, shanghai=5, zhaoshang=5, jiAn=5),
                _make_pool_fund(code="mid", morningstar=3, shanghai=3, zhaoshang=3, jiAn=3)]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_dimension_breakdown_has_exactly_3_dims(self):
        pool = [_make_pool_fund()]
        results = score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "conservative")
        dims = results[0].dimension_breakdown
        assert set(dims.keys()) == {"institutional_consensus", "peer_performance", "fee"}

    def test_money_fund_uses_money_weights(self):
        """Money funds: Stage 1 weights == full weights (3-dim already)."""
        pool = [_make_pool_fund(code="M", fund_type="money", raw_type="货币型")]
        # money category averages
        avgs = {"money": {"ret_1m": 0.1, "ret_3m": 0.3, "ret_6m": 0.6, "ret_1y": 1.5, "ret_3y": 4.0}}
        results = score_funds_light(pool, ScreenConfig(), avgs, "conservative")
        assert len(results) == 1
        assert set(results[0].dimension_breakdown.keys()) == {"institutional_consensus", "peer_performance", "fee"}

    def test_invalid_risk_level_raises(self):
        pool = [_make_pool_fund()]
        with pytest.raises(ValueError):
            score_funds_light(pool, ScreenConfig(), CATEGORY_AVERAGES, "wild")
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/engine/test_screener_light.py -v
```
Expected: FAIL with `ImportError: cannot import name 'score_funds_light'`

**Step 3: Implement `score_funds_light` + `LightResult`**

Add to `src/engine/screener.py` (after `ScreenResult` dataclass, ~line 40):

```python
@dataclass(frozen=True)
class LightResult:
    """Stage 1 result — 3-dim score, no NavStore dependency."""

    code: str
    name: str
    fund_type: str
    score: int  # 0–100, weighted by renormalized Stage 1 weights
    dimension_breakdown: dict[str, int] = field(default_factory=dict)
```

Add to `src/engine/screener.py` (after `score_funds`, ~line 160):

```python
def score_funds_light(
    pool: list["PoolFund"],
    config: ScreenConfig,
    category_averages: dict[str, dict[str, float]],
    risk_level: str = "moderate",
) -> list[LightResult]:
    """Stage 1 scoring — 3 NavStore-free dims (consensus/peer/fee).

    Scores every PoolFund in the pool on institutional_consensus,
    peer_performance, and fee using renormalized weights. No NavStore
    lookup — safe to call on the full 19,747-fund market pool.

    Exclusion rules (same as score_funds):
      - Fund type not in config.allowed_types → skip
      - fee > config.max_fee_rate → skip
      - No category averages for fund type → skip
      - All 4 agency ratings = 0 → skip (InsufficientDataError)
      - No returns → skip (InsufficientDataError)

    Args:
        pool: List of PoolFund (full market or filtered subset).
        config: Screening filters (uses allowed_types + max_fee_rate only;
                min_net_asset_value and min_inception_date are NOT applied
                here — PoolFund lacks those fields. Apply in Stage 2.).
        category_averages: {fund_type: {period: avg_return}}.
        risk_level: "conservative" | "moderate" | "aggressive".

    Returns:
        LightResult list sorted by score descending.
    """
    from src.engine.risk_personalization import get_weights_light
    from src.engine.institutional_consensus import score_institutional_consensus
    from src.engine.peer_scoring import score_peer_performance

    results: list[LightResult] = []

    for pf in pool:
        # ── Hard filters (type + fee only — PoolFund has no NAV/inception) ──
        if pf.fund_type not in config.allowed_types:
            continue
        if Decimal(str(pf.fee)) > config.max_fee_rate:
            continue

        fund_class = classify_fund_type(pf.fund_type)
        weights = get_weights_light(fund_class, risk_level)
        dimensions: dict[str, int] = {}

        # ── Dimension 1: Institutional consensus ─────────────────────
        try:
            ratings = {
                "morningstar": pf.rating_morningstar,
                "shanghai": pf.rating_shanghai,
                "zhaoshang": pf.rating_zhaoshang,
                "jiAn": pf.rating_jiAn,
            }
            dimensions["institutional_consensus"] = score_institutional_consensus(ratings)
        except InsufficientDataError:
            continue  # excluded — no ratings

        # ── Dimension 2: Peer performance ────────────────────────────
        fund_returns = {
            "ret_1m": pf.ret_1m, "ret_3m": pf.ret_3m, "ret_6m": pf.ret_6m,
            "ret_1y": pf.ret_1y, "ret_3y": pf.ret_3y,
        }
        cat_key = pf.raw_type or pf.fund_type
        cat_avg = category_averages.get(cat_key, category_averages.get(pf.fund_type, {}))
        if not cat_avg:
            continue  # excluded — no category averages
        try:
            dimensions["peer_performance"] = score_peer_performance(fund_returns, cat_avg)
        except InsufficientDataError:
            continue  # excluded — no returns

        # ── Dimension 3: Fee ──────────────────────────────────────────
        dimensions["fee"] = _score_fee(Decimal(str(pf.fee)))

        # ── Weighted Stage 1 score ──────────────────────────────────
        score = int(sum(dimensions[d] * weights[d] for d in weights))

        results.append(LightResult(
            code=pf.code, name=pf.name, fund_type=pf.fund_type,
            score=score, dimension_breakdown=dimensions,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/engine/test_screener_light.py -v
```
Expected: 10 passed

**Step 5: Commit**

```bash
git add src/engine/screener.py tests/engine/test_screener_light.py
git commit -m "feat: add score_funds_light for Stage 1 3-dim pool scoring"
```

---

## Task 3: `discover_funds` tool — two-stage pipeline

**Files:**
- Create: `src/tools/discover.py`
- Test: `tests/tools/test_discover.py` (new file)

**Step 1: Write failing tests**

Create `tests/tools/test_discover.py`:

```python
"""Tests for discover_funds MCP tool — two-stage discovery pipeline."""
import pytest
from unittest.mock import patch, MagicMock
from src.tools.discover import discover_funds, _STAGE2_CANDIDATES


class TestDiscoverFunds:
    def test_returns_top_n_results_sorted_by_score(self, monkeypatch):
        """End-to-end: mock pool + nav_store, verify top_n sorted output."""
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index",
                            _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages",
                            lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store",
                            _mock_nav_store)
        result = discover_funds(risk_level="conservative", top_n=3)
        assert result["count"] <= 3
        scores = [r["score"] for r in result["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_allowed_types_filter(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        result = discover_funds(risk_level="conservative", allowed_types="bond", top_n=5)
        for r in result["results"]:
            assert r["type"] == "bond"

    def test_empty_pool_returns_count_zero(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", lambda: {})
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        result = discover_funds(risk_level="conservative")
        assert result["count"] == 0
        assert result["results"] == []

    def test_empty_navstore_returns_error(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        empty_nav = MagicMock()
        empty_nav.coverage_report.return_value = {"fund_count": 0}
        monkeypatch.setattr("src.tools.discover._get_nav_store", lambda: empty_nav)
        result = discover_funds(risk_level="conservative")
        assert "error" in result
        assert "backfill" in result["error"]

    def test_diagnostic_fields_populated(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        result = discover_funds(risk_level="conservative", top_n=3)
        assert "stage1_evaluated" in result
        assert "stage2_evaluated" in result
        assert result["stage1_evaluated"] > 0

    def test_invalid_risk_level_raises(self, monkeypatch):
        monkeypatch.setattr("src.tools.discover._get_or_load_pool_index", _mock_pool_index)
        monkeypatch.setattr("src.tools.discover._get_or_load_category_averages", lambda: _MOCK_AVGS)
        monkeypatch.setattr("src.tools.discover._get_nav_store", _mock_nav_store)
        with pytest.raises(ValueError):
            discover_funds(risk_level="invalid")


# ── Test fixtures ──────────────────────────────────────────────────
from decimal import Decimal
from src.data.sources.fund_pool import PoolFund


def _pf(code, fund_type="bond", morningstar=4, ret_1y=5.0):
    return PoolFund(
        code=code, name=f"Fund {code}", fund_type=fund_type,
        raw_type=fund_type, manager="M", fee=Decimal("0.015"),
        ret_1m=0.5, ret_3m=1.5, ret_6m=3.0, ret_1y=ret_1y, ret_3y=15.0,
        rating_morningstar=morningstar, rating_shanghai=morningstar,
        rating_zhaoshang=morningstar, rating_jiAn=morningstar,
    )


def _mock_pool_index():
    return {f"{i:06d}": _pf(f"{i:06d}", ret_1y=5.0 + i) for i in range(20)}


_MOCK_AVGS = {
    "bond": {"ret_1m": 0.19, "ret_3m": 1.41, "ret_6m": 2.04, "ret_1y": 4.19, "ret_3y": 11.18},
    "mixed": {"ret_1m": 2.0, "ret_3m": 13.0, "ret_6m": 13.0, "ret_1y": 39.0, "ret_3y": 38.0},
}


def _mock_nav_store():
    store = MagicMock()
    store.coverage_report.return_value = {"fund_count": 20}
    store.get_nav_series.return_value = [1.0 + i * 0.001 for i in range(252)]
    return store
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/tools/test_discover.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.discover'`

**Step 3: Implement `discover_funds`**

Create `src/tools/discover.py`:

```python
"""MCP tool: discover_funds — two-stage full-market fund discovery.

Stage 1: light-score all ~19,747 pool funds on 3 NavStore-free dims
         (consensus/peer/fee) → top 200.
Stage 2: enrich those 200 with risk_control + persistence (NavStore)
         and recompute with full 5-dim weights → top_n.
"""
from decimal import Decimal
from datetime import date

from src.datatypes import FundInfo, InsufficientDataError
from src.engine.risk_personalization import classify_fund_type, get_weights
from src.engine.screener import (
    ScreenConfig, ScreenResult, LightResult,
    score_funds_light, score_risk_control, score_consistency, _score_fee,
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
    - min_net_asset_value: 最低规模(元), 默认0不过滤
    - max_fee_rate: 最高费率, 默认0.03 (3%)
    - top_n: 返回前N只, 默认10

    RETURNS: {count, results[], stage1_evaluated, stage2_evaluated, personalized}
    - results: 按 score 降序, 含 5 维度评分 + warnings
    """
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
            "error": "NAV 数据库为空，请先运行回填: python3 -m src.data.sources.nav_store --backfill",
        }

    # ── Load pool + category averages ────────────────────────────────
    pool_index = _get_or_load_pool_index()
    cat_avg_data = _get_or_load_category_averages()
    cat_avg = cat_avg_data.get("broad", {}) if cat_avg_data else {}

    if not pool_index:
        return {"count": 0, "results": [], "stage1_evaluated": 0, "stage2_evaluated": 0}

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
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/tools/test_discover.py -v
```
Expected: 6 passed

**Step 5: Commit**

```bash
git add src/tools/discover.py tests/tools/test_discover.py
git commit -m "feat: add discover_funds two-stage full-market discovery tool"
```

---

## Task 4: Register `discover_funds` in MCP server

**Files:**
- Modify: `src/tools/server.py` (add Tool 17, after `export_report` ~line 563)
- Test: `tests/tools/test_server.py` (if exists; otherwise manual verification)

**Step 1: Write failing test**

Append to `tests/tools/test_server.py` (or create if missing):

```python
def test_discover_funds_tool_registered():
    """Verify discover_funds is exposed as an MCP tool."""
    from src.tools.server import server
    # FastMCP stores tools; verify discover_funds is in the tool list
    tool_names = list(server._tool_manager._tools.keys())
    assert "discover_funds" in tool_names
```

If `tests/tools/test_server.py` doesn't exist, create it with the above test plus:
```python
"""Smoke tests for MCP server tool registration."""
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/tools/test_server.py::test_discover_funds_tool_registered -v
```
Expected: FAIL — `discover_funds` not registered

**Step 3: Register the tool**

Add to `src/tools/server.py` (after the `export_report` tool, before the entry point, ~line 563):

```python
# ── Tool 17: Fund Discovery ───────────────────────────────────────────

@server.tool()
def discover_funds(
    risk_level: str,
    allowed_types: str = "",
    min_net_asset_value: float = 0,
    max_fee_rate: float = 0.03,
    top_n: int = 10,
) -> dict:
    """【全市场基金发现】从 19,747 只基金池中筛选并评分 top N。

    两阶段流水线:
      Stage 1: 3 维度(机构共识/同类业绩/费率)轻量打分全市场 → top 200
      Stage 2: 5 维度(加风控/持续性)全打分 → top N

    WHEN TO USE:
    - "帮我从全市场找最好的债基"
    - "发现规模>5亿的混合基金 top 10"
    - 替代网络搜索建候选池(消除 SEO/流行度偏见)

    HOW TO USE:
    - risk_level: "conservative"|"moderate"|"aggressive" (影响评分权重)
    - allowed_types: 逗号分隔 "bond,mixed,index", 空=全部5类
    - min_net_asset_value: 最低规模(元), 默认0不过滤
    - max_fee_rate: 最高费率, 默认0.03 (3%)
    - top_n: 返回前N只, 默认10

    RETURNS: {count, results[{code, name, type, score, dimension_breakdown, warnings, peer_comparison}],
              stage1_evaluated, stage2_evaluated, personalized}
    - stage1_evaluated: Stage 1 评分的基金数(应≈全市场)
    - stage2_evaluated: Stage 2 评分的基金数(≤200)
    - 注意: net_asset_value/inception_date 返回 None(PoolFund 无此字段),
      买入前请用 audit_single_fund 做完整审计
    """
    from src.tools.discover import discover_funds as _discover_funds
    return _discover_funds(
        risk_level, allowed_types, min_net_asset_value, max_fee_rate, top_n,
    )
```

Also update the module docstring (line 1) — change "16 tools" to "17 tools":
```python
"""Fortress MCP Server — 17 tools across 3 named Agents + 14 supporting tools.
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/tools/test_server.py::test_discover_funds_tool_registered -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/tools/server.py tests/tools/test_server.py
git commit -m "feat: register discover_funds as Tool 17 in MCP server"
```

---

## Task 5: Update docs + full test suite

**Files:**
- Modify: `CODEBUDDY.md` (line 13: "16 个自描述工具" → "17 个")

**Step 1: Update CODEBUDDY.md**

Change line 13:
```
- **MCP 工具**: 17 个自描述工具，覆盖风险测评→配置→筛选→审计→压测→健康→发现全流程
```

**Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all tests pass (existing 426 + new ~21 = ~447)

**Step 3: Smoke-test the tool via Python**

```bash
python -c "
from src.tools.discover import discover_funds
result = discover_funds(risk_level='conservative', allowed_types='bond', top_n=3)
print(f'Stage 1 evaluated: {result.get(\"stage1_evaluated\", \"N/A\")}')
print(f'Stage 2 evaluated: {result.get(\"stage2_evaluated\", \"N/A\")}')
print(f'Returned: {result[\"count\"]} funds')
for r in result['results']:
    print(f'  {r[\"code\"]} {r[\"name\"]} score={r[\"score\"]}')
"
```
Expected: prints stage counts + 3 bond funds with scores.

**Step 4: Commit**

```bash
git add CODEBUDDY.md
git commit -m "docs: update tool count 16→17 in CODEBUDDY.md"
```

---

## Verification Checklist

- [ ] `get_weights_light` returns renormalized weights summing to 1.0 for all 9 combos
- [ ] `score_funds_light` excludes funds with all-zero ratings (no fabrication)
- [ ] `score_funds_light` returns results sorted by score descending
- [ ] `discover_funds` returns top_n sorted by full 5-dim score
- [ ] `discover_funds` respects `allowed_types` filter
- [ ] `discover_funds` returns error when NavStore empty
- [ ] `discover_funds` populates `stage1_evaluated` + `stage2_evaluated` diagnostics
- [ ] Tool registered as "discover_funds" in MCP server
- [ ] CODEBUDDY.md updated to 17 tools
- [ ] Full test suite passes (existing + new)
- [ ] Smoke test prints 3 bond funds with scores

## Open Items (deferred)

1. **PoolFund lacks net_asset_value** — `discover_funds` returns `net_asset_value: None`. Users must run `audit_single_fund` for the scale check (RL-001/005) before buying. Future enhancement: enrich `fetch_fund_pool` to include scale from the rank endpoint.
2. **Stage 2 candidate count fixed at 200** — if Stage 2 returns < top_n after NAV insufficiency exclusions, that's the user's ceiling. Could make adaptive, but YAGNI for now.
3. **No batched lookup_fund** — Stage 2 reads NAV series per-fund via `nav_store.get_nav_series`. 200 sequential SQLite reads ≈ 1-2s acceptable. Could batch if profiling shows need.
