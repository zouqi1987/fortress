"""Shared pytest fixtures for fortress tests."""
from datetime import date
from decimal import Decimal

import pytest

from src.datatypes import FundInfo


@pytest.fixture
def sample_fund() -> FundInfo:
    """A well-established, large-cap fund that passes all audits."""
    return FundInfo(
        code="000001",
        name="稳健大盘混合",
        type="mixed",
        net_asset_value=Decimal("10_000_000_000"),
        fee_rate=Decimal("0.010"),
        inception_date=date(2010, 6, 1),
    )


@pytest.fixture
def tiny_fund() -> FundInfo:
    """A small, new fund that triggers multiple redline warnings."""
    return FundInfo(
        code="000099",
        name="迷你新基金",
        type="stock",
        net_asset_value=Decimal("100_000_000"),
        fee_rate=Decimal("0.025"),
        inception_date=date(2026, 1, 1),
    )


@pytest.fixture
def sample_portfolio() -> dict[str, Decimal]:
    return {
        "equity": Decimal("60000"),
        "bond": Decimal("30000"),
        "cash": Decimal("10000"),
    }
