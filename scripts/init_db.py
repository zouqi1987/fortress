#!/usr/bin/env python3
"""Initialize an empty fortress portfolio database.

Usage:
    python scripts/init_db.py [path]

Default path: data/portfolio.db
"""
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.portfolio_db import PortfolioDB  # noqa: E402


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/portfolio.db"

    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with PortfolioDB(db_path) as db:
        # Schema is auto-created on first use.
        # Insert default cash account so the ledger is immediately usable.
        from src.engine.ledger import Account, AccountType

        db.create_account(
            Account(
                path="assets:cash",
                type=AccountType.ASSET,
                commodity="CNY",
                name="现金账户",
            )
        )

    print(f"✅ Database initialized at: {db_path}")
    print("   Default account: assets:cash (现金账户)")


if __name__ == "__main__":
    main()
