"""SQLite persistence for the three-entity ledger model.

Single-user, synchronous, zero external deps (stdlib sqlite3).
Decimal amounts stored as TEXT to preserve precision.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from typing import Generator

from src.engine.ledger import (
    Account,
    AccountType,
    Split,
    Transaction,
    validate_transaction,
)


class PortfolioDB:
    """CRUD for accounts and transactions backed by SQLite.

    Usage:
        with PortfolioDB("path/to/user.db") as db:
            db.create_account(...)
            txn = db.get_transaction("txn-id")
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # ── Context Manager ──────────────────────────────────────────────

    def __enter__(self) -> PortfolioDB:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        if self._conn is not None:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None
        return False

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("PortfolioDB not used as context manager. Use: with PortfolioDB(...) as db:")
        return self._conn

    # ── Schema ───────────────────────────────────────────────────────

    def _create_schema(self) -> None:
        conn = self._ensure_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                path TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                commodity TEXT NOT NULL,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                description TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS splits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_id TEXT NOT NULL REFERENCES transactions(id),
                account_path TEXT NOT NULL REFERENCES accounts(path),
                amount TEXT NOT NULL,
                memo TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_splits_txn ON splits(txn_id);
            CREATE INDEX IF NOT EXISTS idx_splits_account ON splits(account_path);
            CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date);
            """
        )
        conn.commit()

    # ── Account CRUD ─────────────────────────────────────────────────

    def create_account(self, acct: Account) -> None:
        conn = self._ensure_conn()
        conn.execute(
            "INSERT INTO accounts (path, type, commodity, name) VALUES (?, ?, ?, ?)",
            (acct.path, acct.type.value, acct.commodity, acct.name),
        )
        conn.commit()

    def get_account(self, path: str) -> Account | None:
        conn = self._ensure_conn()
        row = conn.execute("SELECT * FROM accounts WHERE path = ?", (path,)).fetchone()
        if row is None:
            return None
        return Account(
            path=row["path"],
            type=AccountType(row["type"]),
            commodity=row["commodity"],
            name=row["name"],
        )

    def list_accounts(self, type: AccountType | None = None) -> list[Account]:
        conn = self._ensure_conn()
        if type is not None:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE type = ?", (type.value,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM accounts").fetchall()

        return [
            Account(
                path=r["path"],
                type=AccountType(r["type"]),
                commodity=r["commodity"],
                name=r["name"],
            )
            for r in rows
        ]

    # ── Transaction CRUD ─────────────────────────────────────────────

    def create_transaction(self, txn: Transaction) -> None:
        """Create a transaction with all its splits. Validates before writing."""
        # Always validate before persisting
        violations = validate_transaction(txn)
        if violations:
            raise ValueError(
                f"Transaction {txn.id} is invalid: "
                + "; ".join(f"[{v.code}] {v.message}" for v in violations)
            )

        conn = self._ensure_conn()
        conn.execute(
            "INSERT INTO transactions (id, date, description) VALUES (?, ?, ?)",
            (txn.id, txn.date.isoformat(), txn.description),
        )
        for split in txn.splits:
            conn.execute(
                "INSERT INTO splits (txn_id, account_path, amount, memo) VALUES (?, ?, ?, ?)",
                (txn.id, split.account_path, str(split.amount), split.memo),
            )
        conn.commit()

    def get_transaction(self, id: str) -> Transaction | None:
        conn = self._ensure_conn()
        txn_row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (id,)
        ).fetchone()
        if txn_row is None:
            return None

        split_rows = conn.execute(
            "SELECT * FROM splits WHERE txn_id = ? ORDER BY id", (id,)
        ).fetchall()

        splits = tuple(
            Split(
                account_path=s["account_path"],
                amount=Decimal(s["amount"]),
                memo=s["memo"],
            )
            for s in split_rows
        )

        return Transaction(
            id=txn_row["id"],
            date=date.fromisoformat(txn_row["date"]),
            description=txn_row["description"],
            splits=splits,
        )

    def list_transactions(self, start: date, end: date) -> list[Transaction]:
        conn = self._ensure_conn()
        txn_rows = conn.execute(
            "SELECT * FROM transactions WHERE date >= ? AND date <= ? ORDER BY date",
            (start.isoformat(), end.isoformat()),
        ).fetchall()

        if not txn_rows:
            return []

        # Batch load all splits in one query (safe: placeholders are literal "?" only)
        txn_ids = [r["id"] for r in txn_rows]
        if len(txn_ids) > 500:
            # Guard against oversized SQL — paginate if needed
            txn_ids = txn_ids[:500]
        placeholders = ",".join("?" for _ in txn_ids)
        split_rows = conn.execute(
            f"SELECT * FROM splits WHERE txn_id IN ({placeholders}) ORDER BY id",  # nosec
            txn_ids,
        ).fetchall()

        # Group splits by txn_id
        splits_by_txn: dict[str, list[Split]] = {tid: [] for tid in txn_ids}
        for s in split_rows:
            splits_by_txn[s["txn_id"]].append(
                Split(
                    account_path=s["account_path"],
                    amount=Decimal(s["amount"]),
                    memo=s["memo"],
                )
            )

        return [
            Transaction(
                id=r["id"],
                date=date.fromisoformat(r["date"]),
                description=r["description"],
                splits=tuple(splits_by_txn[r["id"]]),
            )
            for r in txn_rows
        ]
