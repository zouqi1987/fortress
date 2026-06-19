"""GnuCash three-entity data model: Account / Transaction / Split.

Zero I/O. Zero dependencies (stdlib only). All amounts are decimal.Decimal.
Delayed constraint validation via validate_transaction().
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import NamedTuple


class AccountType(Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    INCOME = "income"
    EXPENSE = "expense"
    EQUITY = "equity"


class Account(NamedTuple):
    """A GnuCash-style hierarchical account.

    path uses colon-separated hierarchy: "assets:funds:000001"
    """

    path: str
    type: AccountType
    commodity: str  # "CNY" or fund code
    name: str  # human-readable display name


class Split(NamedTuple):
    """One leg of a transaction. Debit = positive amount, credit = negative."""

    account_path: str
    amount: Decimal  # >0 debit, <0 credit
    memo: str = ""


class Transaction(NamedTuple):
    """A complete transaction with at least two splits that sum to zero."""

    id: str
    date: date
    description: str
    splits: tuple[Split, ...]

    def __repr__(self) -> str:
        return f"Transaction(id={self.id!r}, date={self.date}, desc={self.description!r})"


@dataclass(frozen=True)
class Violation:
    """A constraint violation found during delayed validation."""

    txn_id: str
    code: str  # "unbalanced" | "too_few_splits" | "zero_amount"
    message: str


def validate_transaction(txn: Transaction) -> list[Violation]:
    """Run delayed constraint checks on a transaction.

    Returns a list of violations (empty = valid). Does not raise.
    """
    violations: list[Violation] = []

    # Must have at least 2 splits.
    if len(txn.splits) < 2:
        violations.append(
            Violation(
                txn_id=txn.id,
                code="too_few_splits",
                message=f"Transaction must have at least 2 splits, got {len(txn.splits)}",
            )
        )
        return violations  # can't check balance with <2 splits

    # No zero-amount splits.
    for i, split in enumerate(txn.splits):
        if split.amount == Decimal("0"):
            violations.append(
                Violation(
                    txn_id=txn.id,
                    code="zero_amount",
                    message=f"Split {i} ({split.account_path}) has zero amount",
                )
            )

    # Sum must be zero.
    total = sum((s.amount for s in txn.splits), start=Decimal("0"))
    if total != Decimal("0"):
        violations.append(
            Violation(
                txn_id=txn.id,
                code="unbalanced",
                message=f"Transaction splits sum to {total}, must be zero",
            )
        )

    return violations
