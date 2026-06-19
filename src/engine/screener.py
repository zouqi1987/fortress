"""Fund screening and ranking engine.

Zero I/O. Pure functions: receive FundInfo list + config, return scored results.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from src.datatypes import FundInfo, fmt_amount


@dataclass(frozen=True)
class ScreenConfig:
    """Screening parameters. All optional — omit to skip filter."""

    min_net_asset_value: Decimal = Decimal("0")
    allowed_types: frozenset[str] = field(default_factory=lambda: frozenset({"stock", "bond", "mixed", "index", "money"}))
    min_inception_date: date = date(2099, 12, 31)  # far future = no filter by default
    max_fee_rate: Decimal = Decimal("0.03")


@dataclass(frozen=True)
class ScreenResult:
    fund: FundInfo
    score: int  # 0–100, higher = better
    warnings: tuple[str, ...]


def screen_funds(funds: list[FundInfo], config: ScreenConfig) -> list[ScreenResult]:
    """Filter and score a list of funds.

    Returns results sorted by score descending. Funds that fail hard filters
    are excluded entirely. Warnings are informational and don't exclude.
    """
    results: list[ScreenResult] = []

    for fund in funds:
        # ── Hard filters ────────────────────────────────────────────
        if fund.net_asset_value < config.min_net_asset_value:
            continue
        if fund.type not in config.allowed_types:
            continue
        # Exclude funds newer than min_inception_date
        if fund.inception_date > config.min_inception_date:
            continue
        if fund.fee_rate > config.max_fee_rate:
            continue

        # ── Scoring (0–100) ─────────────────────────────────────────
        score = 0
        warnings: list[str] = []

        # Size score (0–30): bigger is better, up to 10B
        size_val = min(fund.net_asset_value, Decimal("10_000_000_000"))
        score += int(size_val * Decimal("30") / Decimal("10_000_000_000"))

        # Age score (0–20): older is better, up to 10 years
        age_days = (date.today() - fund.inception_date).days
        score += min(20, age_days // 180)  # ~0.5 point per half-year

        # Fee score (0–25): lower is better
        if fund.fee_rate <= Decimal("0.005"):
            score += 25
        elif fund.fee_rate <= Decimal("0.010"):
            score += 20
        elif fund.fee_rate <= Decimal("0.015"):
            score += 15
        elif fund.fee_rate <= Decimal("0.020"):
            score += 10
        else:
            score += 5

        # Type diversification bonus (0–15)
        type_bonus = {"bond": 15, "mixed": 12, "index": 10, "stock": 8, "money": 5}
        score += type_bonus.get(fund.type, 5)

        # Remaining to 100: complexity bonus
        score += 10

        # ── Warnings ─────────────────────────────────────────────────
        if fund.net_asset_value < Decimal("200_000_000"):
            warnings.append(f"基金规模 {fmt_amount(fund.net_asset_value)} 低于2亿")
        if (date.today() - fund.inception_date).days < 365:
            warnings.append(f"基金成立不足1年 ({fund.inception_date})")
        if fund.fee_rate > Decimal("0.015"):
            warnings.append(f"费率偏高 ({float(fund.fee_rate):.1%})")  # float() OK: format-only

        results.append(ScreenResult(fund=fund, score=score, warnings=tuple(warnings)))

    results.sort(key=lambda r: r.score, reverse=True)
    return results

