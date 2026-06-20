"""Tests for _is_duplicate_share — share class dedup logic."""
import pytest
from src.data.sources.fund_pool import _is_duplicate_share


class TestIsDuplicateShare:
    """Prove-It: bug where C/D/E/B-only funds were incorrectly excluded."""

    # ── Bug reproduction: C-share without A-equivalent ──────────────

    def test_c_share_with_a_equivalent_is_duplicate(self):
        """C-share with matching A-share → duplicate."""
        all_names = {"某某混合A", "某某混合C", "其他基金A"}
        assert _is_duplicate_share("某某混合C", all_names) is True

    def test_c_share_without_a_equivalent_is_not_duplicate(self):
        """C-share with NO matching A-share → NOT duplicate (the bug fix)."""
        all_names = {"某某混合C", "其他基金A"}  # no "某某混合A" or "某某混合"
        assert _is_duplicate_share("某某混合C", all_names) is False

    def test_c_share_with_base_equivalent_is_duplicate(self):
        """C-share where base name (no suffix) exists → duplicate."""
        all_names = {"某某混合", "某某混合C"}  # base + C
        assert _is_duplicate_share("某某混合C", all_names) is True

    # ── Other suffix types ──────────────────────────────────────────

    def test_d_share_dedup(self):
        all_names = {"测试基金D", "测试基金A"}
        assert _is_duplicate_share("测试基金D", all_names) is True

    def test_e_share_dedup(self):
        all_names = {"测试基金E", "测试基金A"}
        assert _is_duplicate_share("测试基金E", all_names) is True

    def test_b_share_dedup(self):
        all_names = {"测试基金B", "测试基金A"}
        assert _is_duplicate_share("测试基金B", all_names) is True

    def test_lei_c_share_dedup(self):
        """类C suffix variant."""
        all_names = {"某某混合类C", "某某混合类A"}
        assert _is_duplicate_share("某某混合类C", all_names) is True

    # ── Non-suffix names ────────────────────────────────────────────

    def test_no_suffix_not_duplicate(self):
        """Base name with no share class suffix → not duplicate."""
        all_names = {"某某混合", "某某混合A", "某某混合C"}
        assert _is_duplicate_share("某某混合", all_names) is False

    def test_a_share_not_duplicate(self):
        """A-share is the base, never filtered."""
        all_names = {"某某混合A", "某某混合C"}
        assert _is_duplicate_share("某某混合A", all_names) is False

    def test_regular_name_not_duplicate(self):
        """Name without any suffix pattern → not duplicate."""
        all_names = {"沪深300指数增强", "中证500ETF联接"}
        assert _is_duplicate_share("沪深300指数增强", all_names) is False

    # ── Legacy fallback (all_names=None) ────────────────────────────

    def test_legacy_no_all_names_returns_true(self):
        """Without all_names, fall back to always treating C/D/E/B as duplicate."""
        assert _is_duplicate_share("某某混合C") is True
        assert _is_duplicate_share("某某混合D") is True
        assert _is_duplicate_share("某某混合E") is True
        assert _is_duplicate_share("某某混合B") is True
        assert _is_duplicate_share("某某混合类C") is True

    def test_legacy_no_suffix_returns_false(self):
        """Without all_names, non-suffix names are never duplicate."""
        assert _is_duplicate_share("某某混合") is False
        assert _is_duplicate_share("某某混合A") is False
        assert _is_duplicate_share("沪深300指数增强") is False

    # ── Edge cases ──────────────────────────────────────────────────

    def test_empty_all_names_c_share_not_duplicate(self):
        """C-share with empty all_names → not duplicate (no A exists)."""
        assert _is_duplicate_share("独子基金C", set()) is False

    def test_name_ending_in_c_but_not_c_share(self):
        """Name that happens to end with 'C' but isn't a share class suffix."""
        # Chinese fund names don't typically end with Latin chars, but be safe
        all_names = {"ABC", "ABCD"}
        # "ABC" ends with C but is the base name itself → no suffix detected?
        # Actually "ABC" → base="AB", a_equiv="ABA" → neither in all_names → False
        # This is correct: "ABC" isn't a C-share of "AB"
        assert _is_duplicate_share("ABC", all_names) is False
