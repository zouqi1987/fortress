# Screener v2 Development Plan

> 2026-06-20 | Three-layer scoring: static + performance + macro overlay

## Dependency Graph

```
data/sources/manager.py (independent — HTML parsing)
    │
engine/macro_overlay.py (independent — sina index)
    │
engine/screener.py (upgrade — depends on NAV + manager + macro)
```

## Vertical Slices

### T1: Fund Manager Crawler — `data/sources/manager.py`
- [ ] Parse `fundf10.eastmoney.com/jjjl_CODE.html` for manager info
- [ ] Extract: name, tenure_days, cumulative_return, fund_count
- [ ] `ManagerInfo` dataclass
- [ ] Test: `tests/data/test_manager.py` — parse known fund, verify fields
- **Checkpoint**: `python -c "from src.data.sources.manager import fetch_manager; print(fetch_manager('000001'))"`

### T2: Macro Overlay — `engine/macro_overlay.py`
- [ ] `detect_regime() -> MarketRegime` (bull/bear/sideways)
- [ ] `get_multiplier(regime, risk_level) -> Decimal`
- [ ] Bull: 1.0, Sideways: 0.8, Bear: 0.6
- [ ] Test: `tests/engine/test_macro_overlay.py` — mock index data, verify regime detection
- **Checkpoint**: `python -c "from src.engine.macro_overlay import detect_regime; print(detect_regime())"`

### T3: Screener Upgrade — `engine/screener.py`
- [ ] `PerformanceScore(returns, drawdown, consistency)` dataclass
- [ ] `score_returns(nav_data) -> dict` — multi-period weighted
- [ ] `score_risk(nav_data) -> dict` — Sharpe + Sortino + drawdown
- [ ] `score_consistency(nav_data) -> dict` — quarterly win rate
- [ ] `score_manager(manager_info) -> dict` — tenure + return
- [ ] New `screen_funds_v2(funds, nav_data, config)` — 100-point scale
- [ ] Keep old `screen_funds` backward compatible
- **Checkpoint**: Run on 003026/002650/006332, verify scores differ from v1

### T4: Integration + Tests
- [ ] Test all 3 funds with v2 screener
- [ ] Compare v1 vs v2 rankings
- [ ] 180 unit tests still pass
- **Checkpoint**: Full `pytest tests/ -k "not integration"` green

## New Files
```
src/data/sources/manager.py      ~60 lines
src/engine/macro_overlay.py      ~50 lines
tests/data/test_manager.py       ~30 lines
tests/engine/test_macro_overlay.py ~30 lines
tests/engine/test_screener_v2.py ~50 lines
```

## Modified Files
```
src/engine/screener.py           +120 lines (new scoring functions)
```

## Scoring Formula

| Dimension | Points | Metrics |
|-----------|--------|---------|
| Static (size/age/fee/type) | 40 | Existing logic, scaled down from 100 |
| Risk-Adjusted Return | 25 | 1m/3m/6m/1y/3y returns, weighted (recent > old), peer-relative |
| Risk Control | 20 | Max drawdown (3m/6m/1y), Sortino ratio, volatility |
| Consistency | 10 | Quarterly positive rate, max consecutive winning quarters |
| Manager | 5 | Tenure, cumulative return, fund count |
| **Total** | **100** | |

Macro Overlay: independent multiplier applied to final recommendation, 不修改基金分数.
