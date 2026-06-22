"""Category peer benchmark — compute peer averages from fund pool data.

Zero I/O. Pure functions: receive PoolFund list, return category averages.
Used by screen_funds for peer comparison and report context for display.
"""

from src.data.sources.fund_pool import PoolFund

PERIODS = ("ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_3y")


def compute_category_averages(
    funds: list[PoolFund],
    group_by: str = "broad",
) -> dict[str, dict[str, float]]:
    """Return {category: {period: avg_return_pct}} for each category.

    Groups funds by classification, computes arithmetic mean per period.
    An empty input returns {}.

    Args:
        funds: List of PoolFund objects (from fund pool).
        group_by: "broad" (default) — uses fund_type (5 categories: bond/mixed/...).
                  "raw" — uses raw_type (29 categories: 债券型-长债/混合型-偏股/...).

    Returns:
        Nested dict keyed by category string → period name → average.
    """
    if not funds:
        return {}

    attr = "raw_type" if group_by == "raw" else "fund_type"

    # Group by type
    groups: dict[str, list[PoolFund]] = {}
    for f in funds:
        key = getattr(f, attr, f.fund_type)
        groups.setdefault(key, []).append(f)

    # Compute averages per group per period
    result: dict[str, dict[str, float]] = {}
    for gtype, group in groups.items():
        if not group:
            continue
        avgs: dict[str, float] = {}
        for period in PERIODS:
            values = [getattr(f, period, 0.0) for f in group]
            avgs[period] = sum(values) / len(values)
        result[gtype] = avgs

    return result
