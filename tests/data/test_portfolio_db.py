"""Tests for src/data/portfolio_db.py — SQLite CRUD for accounts and transactions."""
from datetime import date
from decimal import Decimal

import pytest

from src.data.portfolio_db import PortfolioDB
from src.engine.ledger import Account, AccountType, Split, Transaction, validate_transaction


@pytest.fixture
def db(tmp_path):
    """Create a fresh PortfolioDB for each test."""
    with PortfolioDB(str(tmp_path / "test.db")) as db:
        yield db


class TestAccountCRUD:
    def test_create_and_get_account(self, db):
        acct = Account(
            path="assets:funds:000001",
            type=AccountType.ASSET,
            commodity="000001",
            name="华夏成长混合",
        )
        db.create_account(acct)
        result = db.get_account("assets:funds:000001")
        assert result is not None
        assert result.name == "华夏成长混合"
        assert result.type == AccountType.ASSET

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_account("nonexistent") is None

    def test_list_all_accounts(self, db):
        db.create_account(Account("assets:cash", AccountType.ASSET, "CNY", "现金"))
        db.create_account(Account("expenses:fee", AccountType.EXPENSE, "CNY", "手续费"))
        db.create_account(Account("income:dividend", AccountType.INCOME, "CNY", "分红"))

        all_accts = db.list_accounts()
        assert len(all_accts) == 3

    def test_list_by_type(self, db):
        db.create_account(Account("assets:cash", AccountType.ASSET, "CNY", "现金"))
        db.create_account(Account("expenses:fee", AccountType.EXPENSE, "CNY", "手续费"))

        assets = db.list_accounts(type=AccountType.ASSET)
        assert len(assets) == 1
        assert assets[0].path == "assets:cash"

    def test_duplicate_account_raises(self, db):
        acct = Account("assets:cash", AccountType.ASSET, "CNY", "现金")
        db.create_account(acct)
        with pytest.raises(Exception):
            db.create_account(acct)


class TestTransactionCRUD:
    def test_create_and_get_transaction(self, db):
        db.create_account(Account("assets:funds:000001", AccountType.ASSET, "000001", "fund"))
        db.create_account(Account("assets:cash", AccountType.ASSET, "CNY", "cash"))

        txn = Transaction(
            id="txn-001",
            date=date(2025, 6, 19),
            description="申购基金",
            splits=(
                Split("assets:funds:000001", Decimal("10000.00"), "申购"),
                Split("assets:cash", Decimal("-10000.00"), "扣款"),
            ),
        )
        db.create_transaction(txn)
        result = db.get_transaction("txn-001")
        assert result is not None
        assert result.description == "申购基金"
        assert len(result.splits) == 2

    def test_create_unbalanced_transaction_raises(self, db):
        db.create_account(Account("assets:cash", AccountType.ASSET, "CNY", "cash"))
        db.create_account(Account("assets:funds:000001", AccountType.ASSET, "000001", "fund"))

        txn = Transaction(
            id="txn-002",
            date=date(2025, 6, 19),
            description="unbalanced",
            splits=(
                Split("assets:funds:000001", Decimal("10000.00")),
                Split("assets:cash", Decimal("-9000.00")),
            ),
        )
        with pytest.raises(ValueError, match="unbalanced"):
            db.create_transaction(txn)

    def test_list_transactions_by_date_range(self, db):
        db.create_account(Account("assets:cash", AccountType.ASSET, "CNY", "cash"))
        db.create_account(Account("assets:funds:000001", AccountType.ASSET, "000001", "fund"))

        txn1 = Transaction(
            id="txn-jan",
            date=date(2025, 1, 15),
            description="January purchase",
            splits=(
                Split("assets:funds:000001", Decimal("5000.00")),
                Split("assets:cash", Decimal("-5000.00")),
            ),
        )
        txn2 = Transaction(
            id="txn-mar",
            date=date(2025, 3, 20),
            description="March purchase",
            splits=(
                Split("assets:funds:000001", Decimal("3000.00")),
                Split("assets:cash", Decimal("-3000.00")),
            ),
        )
        db.create_transaction(txn1)
        db.create_transaction(txn2)

        results = db.list_transactions(date(2025, 2, 1), date(2025, 6, 1))
        assert len(results) == 1
        assert results[0].id == "txn-mar"

    def test_get_nonexistent_transaction_returns_none(self, db):
        assert db.get_transaction("no-such-txn") is None


class TestContextManager:
    def test_enter_exit(self, tmp_path):
        with PortfolioDB(str(tmp_path / "ctx.db")) as db:
            db.create_account(Account("assets:cash", AccountType.ASSET, "CNY", "现金"))
            result = db.get_account("assets:cash")
            assert result is not None

    def test_reuse_connection(self, tmp_path):
        with PortfolioDB(str(tmp_path / "reuse.db")) as db:
            db.create_account(Account("assets:cash", AccountType.ASSET, "CNY", "现金"))

        # After exit, new context manager creates fresh connection
        with PortfolioDB(str(tmp_path / "reuse.db")) as db:
            result = db.get_account("assets:cash")
            assert result is not None
