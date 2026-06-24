"""Institutional consensus scoring — composite from agency ratings.

Zero I/O. Pure function: receives agency ratings dict, returns 0-100 score.
Used by the unified screener as one of 5 scoring dimensions.

Morningstar Medalist methodology weights People+Process+Parent at 90% for active
funds — the 4 agency ratings in PoolFund ARE that professional consensus. We average
the available ratings rather than reinventing qualitative judgment.
"""
from src.datatypes import InsufficientDataError


def score_institutional_consensus(ratings: dict[str, float]) -> int:
    """Score institutional consensus 0-100 from agency ratings.

    Each rating is 0-5 (0 = unrated by that agency). Only non-zero ratings
    count toward the average — a fund rated by 1 agency at 4/5 scores 80,
    not 20 (4/20).

    Args:
        ratings: {"morningstar": 4, "shanghai": 3, "zhaoshang": 0, "jiAn": 5}
                 Missing keys treated as 0 (unrated).

    Returns:
        0-100 score (avg_rating * 20).

    Raises:
        InsufficientDataError: If no agency has rated the fund (all 0 or empty).
    """
    valid = {k: v for k, v in ratings.items() if v > 0}
    if not valid:
        raise InsufficientDataError("无机构评级")
    avg = sum(valid.values()) / len(valid)
    return min(100, int(avg * 20))
