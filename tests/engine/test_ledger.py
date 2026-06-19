"""Tests for src/engine/ledger.py — three-entity data model + delayed constraint validation."""
from datetime import date
from decimal import Decimal

import pytest

from src.engine.ledger import (
    Account,
    AccountType,
    Split,
    Transaction,
    Violation,
    validate_transaction,
)


class TestAccount:
    def test_create_asset_account(self):
        acct = Account(
            path="assets:funds:000001",
            type=AccountType.ASSET,
            commodity="000001",
            name="华夏成长混合",
        )
        assert acct.path == "assets:funds:000001"
        assert acct.type == AccountType.ASSET

    def test_account_immutable(self):
        acct = Account(
            path="assets:cash",
            type=AccountType.ASSET,
            commodity="CNY",
            name="现金",
        )
        with pytest.raises(AttributeError):
            acct.name = "修改后的名称"  # type: ignore[misc]


class TestSplit:
    def test_debit_split_positive(self):
        split = Split(
            account_path="assets:funds:000001",
            amount=Decimal("10000.00"),
            memo="申购",
        )
        assert split.amount > Decimal("0")

    def test_credit_split_negative(self):
        split = Split(
            account_path="assets:cash",
            amount=Decimal("-10000.00"),
            memo="扣款",
        )
        assert split.amount < Decimal("0")


class TestTransaction:
    def test_create_balanced_transaction(self):
        txn = Transaction(
            id="txn-001",
            date=date(2025, 6, 19),
            description="申购华夏成长混合 10000 元",
            splits=(
                Split("assets:funds:000001", Decimal("10000.00"), "申购"),
                Split("assets:cash", Decimal("-10000.00"), "扣款"),
            ),
        )
        assert len(txn.splits) == 2
        assert txn.date == date(2025, 6, 19)


class TestValidateTransaction:
    """Delayed constraint validation — no I/O, pure function."""

    def test_balanced_transaction_passes(self):
        txn = Transaction(
            id="txn-001",
            date=date(2025, 6, 19),
            description="balanced",
            splits=(
                Split("assets:funds:000001", Decimal("10000.00")),
                Split("assets:cash", Decimal("-10000.00")),
            ),
        )
        violations = validate_transaction(txn)
        assert len(violations) == 0

    def test_unbalanced_transaction_fails(self):
        txn = Transaction(
            id="txn-002",
            date=date(2025, 6, 19),
            description="unbalanced",
            splits=(
                Split("assets:funds:000001", Decimal("10000.00")),
                Split("assets:cash", Decimal("-9999.00")),
            ),
        )
        violations = validate_transaction(txn)
        assert len(violations) >= 1
        assert any(v.code == "unbalanced" for v in violations)

    def test_single_split_fails(self):
        txn = Transaction(
            id="txn-003",
            date=date(2025, 6, 19),
            description="only one split",
            splits=(Split("assets:cash", Decimal("100.00")),),
        )
        violations = validate_transaction(txn)
        assert any(v.code == "too_few_splits" for v in violations)

    def test_zero_amount_split_fails(self):
        txn = Transaction(
            id="txn-004",
            date=date(2025, 6, 19),
            description="zero amount",
            splits=(
                Split("assets:funds:000001", Decimal("0.00")),
                Split("assets:cash", Decimal("0.00")),
            ),
        )
        violations = validate_transaction(txn)
        assert any(v.code == "zero_amount" for v in violations)

    def test_three_way_balanced_transaction_passes(self):
        txn = Transaction(
            id="txn-005",
            date=date(2025, 6, 19),
            description="申购 + 手续费",
            splits=(
                Split("assets:funds:000001", Decimal("10000.00")),
                Split("assets:cash", Decimal("-10015.00")),
                Split("expenses:fee", Decimal("15.00")),
            ),
        )
        violations = validate_transaction(txn)
        assert len(violations) == 0

    def test_violation_has_txn_id(self):
        txn = Transaction(
            id="txn-006",
            date=date(2025, 6, 19),
            description="unbalanced",
            splits=(
                Split("assets:funds:000001", Decimal("100.00")),
                Split("assets:cash", Decimal("-99.00")),
            ),
        )
        violations = validate_transaction(txn)
        for v in violations:
            assert v.txn_id == "txn-006"

    def test_empty_splits_fails(self):
        txn = Transaction(
            id="txn-007",
            date=date(2025, 6, 19),
            description="no splits",
            splits=(),
        )
        violations = validate_transaction(txn)
        assert any(v.code == "too_few_splits" for v in violations)
