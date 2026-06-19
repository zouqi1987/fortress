"""Tests for src/datatypes.py — shared types and helpers."""
from datetime import date
from decimal import Decimal

import pytest

from src.datatypes import (
    FundInfo,
    IndexPoint,
    NAVPoint,
    classify_fund_type,
    fmt_amount,
)


class TestFundInfo:
    def test_frozen_dataclass(self):
        f = FundInfo("000001", "test", "mixed", Decimal("1e9"), Decimal("0.01"), date(2020, 1, 1))
        with pytest.raises(Exception):  # frozen
            f.name = "changed"  # type: ignore[misc]


class TestNAVPoint:
    def test_frozen(self):
        n = NAVPoint(date(2025, 6, 19), Decimal("1.5"), Decimal("2.0"))
        assert n.nav == Decimal("1.5")


class TestIndexPoint:
    def test_frozen(self):
        i = IndexPoint(date(2025, 6, 19), Decimal("3500"), Decimal("1e8"))
        assert i.close == Decimal("3500")


class TestClassifyFundType:
    def test_stock(self):
        assert classify_fund_type("股票型") == "stock"
        assert classify_fund_type("stock") == "stock"

    def test_index(self):
        assert classify_fund_type("指数型") == "index"
        assert classify_fund_type("index fund") == "index"

    def test_bond(self):
        assert classify_fund_type("债券型") == "bond"

    def test_money(self):
        assert classify_fund_type("货币市场基金") == "money"

    def test_mixed(self):
        assert classify_fund_type("混合型") == "mixed"

    def test_unknown(self):
        assert classify_fund_type("") == "unknown"
        assert classify_fund_type("外星基金") == "unknown"


class TestFmtAmount:
    def test_zero(self):
        assert fmt_amount(Decimal("0")) == "0元"

    def test_wan(self):
        assert "万" in fmt_amount(Decimal("50000"))

    def test_yi(self):
        assert "亿" in fmt_amount(Decimal("500_000_000"))
