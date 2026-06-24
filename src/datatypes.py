"""Shared data types used by both engine/ and data/ layers.

Zero-dependency leaf module. All data types are frozen dataclasses;
InsufficientDataError is the sole exception class.
engine/ and data/ both import from here — no cross-layer imports.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class InsufficientDataError(Exception):
    """Raised when a fund lacks required data for scoring — caller must exclude, not fabricate."""


@dataclass(frozen=True)
class NAVPoint:
    """Single-day fund NAV record."""
    date: date
    nav: Decimal  # 单位净值
    acc_nav: Decimal  # 累计净值


@dataclass(frozen=True)
class FundInfo:
    """Fund basic information for screening and audit."""
    code: str
    name: str
    type: str  # "stock" | "bond" | "mixed" | "index" | "money"
    net_asset_value: Decimal  # 基金规模 (元)
    fee_rate: Decimal
    inception_date: date


@dataclass(frozen=True)
class IndexPoint:
    """Single-day index market data."""
    date: date
    close: Decimal
    volume: Decimal


def fmt_amount(amount: Decimal) -> str:
    """Format Decimal amount in Chinese units (亿/万)."""
    if amount == Decimal("0"):
        return "0元"
    yi = Decimal("100_000_000")
    if amount >= yi:
        return f"{float(amount / yi):.1f}亿"
    wan = Decimal("10_000")
    return f"{float(amount / wan):.0f}万"


def classify_fund_type(raw: str) -> str:
    """Map Chinese fund type descriptions to our classification.

    Returns "unknown" for unrecognized input instead of silently guessing.
    """
    if not raw or not raw.strip():
        return "unknown"
    raw_lower = raw.lower().strip()
    if any(k in raw_lower for k in ("指数", "index")):
        return "index"
    if any(k in raw_lower for k in ("股票", "stock")):
        return "stock"
    if any(k in raw_lower for k in ("债券", "bond")):
        return "bond"
    if any(k in raw_lower for k in ("货币", "money", "货币市场")):
        return "money"
    if any(k in raw_lower for k in ("混合", "mixed", "平衡")):
        return "mixed"
    return "unknown"
