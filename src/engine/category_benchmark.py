"""Category peer benchmark — compute peer averages from fund pool data.

Zero I/O. Pure functions: receive PoolFund list, return category averages.
Used by screen_funds for peer comparison and report context for display.
"""

from src.data.sources.fund_pool import PoolFund

PERIODS = ("ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_3y")


def compute_category_averages(
    funds: list[PoolFund],
) -> dict[str, dict[str, float]]:
    """Return {fund_type: {period: avg_return_pct}} for each category.

    Groups funds by fund_type, computes arithmetic mean per period.
    Funds with all-zero returns are included (they represent the real
    market distribution). An empty input returns {}.

    Args:
        funds: List of PoolFund objects (from fund pool).

    Returns:
        Nested dict keyed by fund_type string → period name → average.
        Example: {"bond": {"ret_1y": 5.4, ...}, "mixed": {"ret_1y": 12.1, ...}}
    """
    if not funds:
        return {}

    # Group by type
    groups: dict[str, list[PoolFund]] = {}
    for f in funds:
        groups.setdefault(f.fund_type, []).append(f)

    # Compute averages per group per period
    result: dict[str, dict[str, float]] = {}
    for ftype, group in groups.items():
        if not group:
            continue
        avgs: dict[str, float] = {}
        for period in PERIODS:
            values = [getattr(f, period, 0.0) for f in group]
            avgs[period] = sum(values) / len(values)
        result[ftype] = avgs

    return result
