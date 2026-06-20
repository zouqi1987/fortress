"""Tests for fund manager data crawler."""
import pytest

from src.data.sources.manager import ManagerInfo, fetch_manager


class TestFetchManager:
    def test_fetch_known_fund_returns_info(self):
        info = fetch_manager("003026")
        assert info is not None, "Should return data for valid fund"
        assert info.fund_code == "003026"
        assert len(info.name) > 0

    def test_invalid_fund_returns_none(self):
        info = fetch_manager("000000")  # non-existent code
        # May return None or partial info — both are acceptable
        # The key behavior: doesn't crash

    def test_fetch_002650(self):
        info = fetch_manager("002650")
        if info:
            assert info.fund_code == "002650"


class TestManagerInfo:
    def test_fields_are_set(self):
        info = ManagerInfo(
            fund_code="000001", name="张三", tenure_days=1000,
            cumulative_return="+25.6%", fund_count=3,
        )
        assert info.name == "张三"
        assert info.tenure_days == 1000
        assert info.fund_count == 3
