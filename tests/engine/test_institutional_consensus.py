"""Tests for institutional consensus scoring — score_institutional_consensus().

Zero I/O pure function: takes agency ratings, returns 0-100 consensus score.
All-zero ratings → InsufficientDataError (fund must be excluded, not scored).
"""
import pytest

from src.datatypes import InsufficientDataError
from src.engine.institutional_consensus import score_institutional_consensus


class TestScoreInstitutionalConsensus:
    def test_all_max_ratings_scores_100(self):
        """4 agencies all rate 5/5 → score 100."""
        ratings = {"morningstar": 5, "shanghai": 5, "zhaoshang": 5, "jiAn": 5}
        assert score_institutional_consensus(ratings) == 100

    def test_all_unrated_raises_insufficient_data(self):
        """All 4 ratings are 0 (unrated) → InsufficientDataError, not a score."""
        ratings = {"morningstar": 0, "shanghai": 0, "zhaoshang": 0, "jiAn": 0}
        with pytest.raises(InsufficientDataError, match="无机构评级"):
            score_institutional_consensus(ratings)

    def test_partial_unrated_averages_only_valid(self):
        """2 of 4 unrated → average the 2 rated, not penalized by zeros.

        morningstar=4, shanghai=3, zhaoshang=0, jiAn=0
        → avg(4,3) = 3.5 → 3.5 * 20 = 70
        """
        ratings = {"morningstar": 4, "shanghai": 3, "zhaoshang": 0, "jiAn": 0}
        assert score_institutional_consensus(ratings) == 70

    def test_single_rated_uses_that_value(self):
        """Only 1 agency rated → use it alone.

        morningstar=4, rest 0 → 4 * 20 = 80
        """
        ratings = {"morningstar": 4, "shanghai": 0, "zhaoshang": 0, "jiAn": 0}
        assert score_institutional_consensus(ratings) == 80

    def test_all_mid_ratings_scores_60(self):
        """4 agencies all rate 3/5 → score 60."""
        ratings = {"morningstar": 3, "shanghai": 3, "zhaoshang": 3, "jiAn": 3}
        assert score_institutional_consensus(ratings) == 60

    def test_missing_keys_treated_as_unrated(self):
        """Dict missing keys → treated as 0 (unrated), not crash.

        Only morningstar present with value 5 → 5 * 20 = 100
        """
        ratings = {"morningstar": 5}
        assert score_institutional_consensus(ratings) == 100

    def test_empty_dict_raises(self):
        """Empty ratings dict → no data → InsufficientDataError."""
        with pytest.raises(InsufficientDataError):
            score_institutional_consensus({})

    def test_out_of_range_rating_clamped_to_100(self):
        """Rating > 5 (malformed API data) → score clamped to 100, not 120+.

        Defense at boundary: akshare data is untrusted; a corrupt rating of 6
        must not produce a score > 100 that could mislead an investor.
        """
        ratings = {"morningstar": 6, "shanghai": 0, "zhaoshang": 0, "jiAn": 0}
        assert score_institutional_consensus(ratings) == 100
