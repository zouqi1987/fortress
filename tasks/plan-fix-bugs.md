# Bug Fix Plan — Test Anomalies

> 2026-06-20 | 3 bugs found during live testing

## Bug 1: NAV 数据只有 20 条
**Root cause**: `_eastmoney_base.fetch_fund_nav` page_size=100, but eastmoney API may return fewer. Date filter or pagination logic wrong.
**Fix**: 
- Add debug logging to see actual API response count
- Investigate if `start`/`end` format needs `YYYY-MM-DD` (not `YYYYMMDD`)
- Verify page loop increments correctly

## Bug 2: 健康评分漂移目标与风险评估不一致
**Root cause**: risk_profile suggests E60/B30/C10 for moderate; health_checker targets E50/B40/C10. Two sources of truth.
**Fix**: Align health_checker `_TARGETS` with risk_profile `_allocation_from_score` values.

## Bug 3: 多空信号与健康评分对分散度判断矛盾
**Root cause**: signals.py says 3 holdings = "分散度合理" (bull); health_checker says 3 = "持仓数量过少" (warning).
**Fix**: Unify threshold — both use 4-8 as optimal range. signals.py: <4 → bear.
