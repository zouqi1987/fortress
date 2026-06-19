"""Tests for src/engine/auditor.py — single-product audit rules."""
from datetime import date
from decimal import Decimal

import pytest

from src.data.market import FundInfo
from src.engine.auditor import AuditResult, audit_fund


class TestAuditFund:
    def test_large_established_fund_passes(self):
        fund = FundInfo(
            "000001", "稳健大盘", "mixed",
            Decimal("10_000_000_000"), Decimal("0.010"),
            date(2010, 1, 1),
        )
        result = audit_fund(fund, Decimal("50000"))
        assert result.passed
        assert result.severity == "pass"

    def test_tiny_fund_with_large_position_warns(self):
        fund = FundInfo(
            "000002", "迷你基金", "stock",
            Decimal("100_000_000"), Decimal("0.025"),
            date(2023, 6, 1),
        )
        result = audit_fund(fund, Decimal("200000"))
        assert not result.passed
        assert any("规模" in r for r in result.reasons)

    def test_new_fund_warns(self):
        fund = FundInfo(
            "000003", "新基金", "mixed",
            Decimal("5_000_000_000"), Decimal("0.015"),
            date(2026, 1, 1),  # ~5 months old
        )
        result = audit_fund(fund, Decimal("10000"))
        assert not result.passed
        assert any("成立" in r or "age" in r.lower() for r in result.reasons)

    def test_high_fee_fund_warns(self):
        fund = FundInfo(
            "000004", "高费率基金", "stock",
            Decimal("5_000_000_000"), Decimal("0.025"),
            date(2015, 1, 1),
        )
        result = audit_fund(fund, Decimal("10000"))
        assert not result.passed
        assert any("费率" in r or "fee" in r.lower() for r in result.reasons)

    def test_no_position_limit_issue_for_small_amount(self):
        fund = FundInfo(
            "000005", "小型基金", "bond",
            Decimal("150_000_000"), Decimal("0.005"),
            date(2018, 1, 1),
        )
        result = audit_fund(fund, Decimal("10000"))
        # Small position in small fund — should pass (position is within limit)
        assert result.passed

    def test_concentration_warning(self):
        fund = FundInfo(
            "000006", "普通基金", "index",
            Decimal("5_000_000_000"), Decimal("0.008"),
            date(2018, 1, 1),
        )
        result = audit_fund(fund, Decimal("300000"), total_portfolio=Decimal("500000"))
        assert not result.passed
        assert any("集中" in r or "concentration" in r.lower() for r in result.reasons)

    def test_stock_fund_never_recommended(self):
        """Per our constraint: never recommend individual stocks. Stock funds are OK."""
        fund = FundInfo(
            "000007", "股票型基金", "stock",
            Decimal("10_000_000_000"), Decimal("0.012"),
            date(2010, 1, 1),
        )
        result = audit_fund(fund, Decimal("50000"))
        # Stock FUNDS are allowed (not individual stocks)
        assert result.passed
