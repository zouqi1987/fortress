"""Peer-relative performance scoring — fund vs. category averages.

Zero I/O. Pure function: receives pre-calculated returns, returns 0-100 score
where 50 = peer average, >50 beats peers, <50 lags. Used by the unified
screener as one of the scoring dimensions.

Methodology: weighted excess return (fund - category_avg) across 5 lookback
periods, linearly mapped via score = 50 + weighted_excess * 2, clamped to
[0, 100]. Long horizons (ret_1y) carry the most weight — they are the most
statistically meaningful for distinguishing manager skill from short-term noise.
"""
from src.datatypes import InsufficientDataError

PERIOD_WEIGHTS: dict[str, float] = {
    "ret_1m": 0.10,
    "ret_3m": 0.15,
    "ret_6m": 0.20,
    "ret_1y": 0.35,
    "ret_3y": 0.20,
}

# Scale: +10pp weighted excess → 50 + 10*2 = 70. Linear, symmetric around 50.
_SCALE_FACTOR = 2.0
_NEUTRAL_SCORE = 50


def score_peer_performance(
    fund_returns: dict[str, float],
    category_averages: dict[str, float],
    period_weights: dict[str, float] = PERIOD_WEIGHTS,
) -> int:
    """Score peer-relative performance 0-100 from pre-calculated returns.

    Computes weighted excess (fund - category_avg) across the 5 lookback
    periods, then maps linearly: score = 50 + weighted_excess * 2, clamped to
    [0, 100]. A missing period in ``fund_returns`` contributes 0 excess for
    that period (graceful, not crash) — a fund with no 1-month return is not
    penalized, it just gets no credit/penalty from that horizon.

    Args:
        fund_returns: {"ret_1m": 1.2, "ret_3m": 3.1, ...} in percentage points.
                      Keys may be a subset of the 5 periods; missing → 0 excess.
        category_averages: Same shape as fund_returns; peer averages per period.
        period_weights: Weights per period, default PERIOD_WEIGHTS (sums to 1.0).

    Returns:
        0-100 integer score. 50 = peer average, >50 beats peers, <50 lags.
    """
    import math

    weighted_excess = 0.0
    matched_periods = 0
    for period, weight in period_weights.items():
        if period not in fund_returns:
            # Graceful: missing period → 0 excess for this period.
            continue
        fund_val = fund_returns[period]
        cat_val = category_averages.get(period, 0.0)
        # Guard against NaN (akshare returns NaN for some funds/periods)
        if isinstance(fund_val, float) and math.isnan(fund_val):
            continue
        if isinstance(cat_val, float) and math.isnan(cat_val):
            cat_val = 0.0
        matched_periods += 1
        weighted_excess += (fund_val - cat_val) * weight

    if matched_periods == 0:
        raise InsufficientDataError("无收益率数据")

    score = _NEUTRAL_SCORE + weighted_excess * _SCALE_FACTOR
    return min(100, max(0, int(round(score))))
