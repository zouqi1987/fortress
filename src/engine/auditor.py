"""Single-product audit engine with redline rule checks.

Zero I/O. Takes FundInfo + planned position, returns AuditResult.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.datatypes import FundInfo, fmt_amount

# ── Rule constants ───────────────────────────────────────────────────

MIN_FUND_SIZE = Decimal("200_000_000")  # 2亿
MAX_POSITION_IN_SMALL_FUND = Decimal("50_000")  # 5万
MIN_FUND_AGE_DAYS = 365  # 1 year
MAX_FEE_RATE = Decimal("0.015")  # 1.5%
MAX_CONCENTRATION_PCT = Decimal("0.20")  # 20% of portfolio


@dataclass(frozen=True)
class AuditResult:
    fund_code: str
    passed: bool
    severity: str  # "pass" | "warn" | "reject"
    reasons: tuple[str, ...]


def audit_fund(
    fund: FundInfo,
    planned_amount: Decimal,
    total_portfolio: Decimal | None = None,
) -> AuditResult:
    """Audit a single fund against redline rules.

    Args:
        fund: Fund information from market data.
        planned_amount: Planned investment amount in CNY.
        total_portfolio: Total portfolio value (for concentration check).

    Returns:
        AuditResult with pass/warn/reject and reasons.
    """
    reasons: list[str] = []
    severity = "pass"

    # RL-001: Small fund, large position
    if fund.net_asset_value < MIN_FUND_SIZE:
        if planned_amount > MAX_POSITION_IN_SMALL_FUND:
            reasons.append(
                f"基金规模 {fmt_amount(fund.net_asset_value)} < 2亿，"
                f"单客户持仓不得超过5万 (计划 {fmt_amount(planned_amount)})"
            )
            severity = "reject"

    # RL-002: Fund too new
    fund_age_days = (date.today() - fund.inception_date).days
    if fund_age_days < MIN_FUND_AGE_DAYS:
        reasons.append(
            f"基金成立不足1年 ({fund.inception_date}，仅{fund_age_days}天)"
        )
        if severity == "pass":
            severity = "warn"

    # RL-003: Fee too high
    if fund.fee_rate > MAX_FEE_RATE:
        reasons.append(
            f"费率 {float(fund.fee_rate):.2%} 超过 {float(MAX_FEE_RATE):.1%}"
        )
        if severity == "pass":
            severity = "warn"

    # RL-004: Concentration risk
    if total_portfolio is not None and total_portfolio > Decimal("0"):
        if planned_amount / total_portfolio > MAX_CONCENTRATION_PCT:
            pct = float(planned_amount / total_portfolio * 100)
            reasons.append(
                f"单品集中度 {pct:.0f}% 超过 20% 上限"
            )
            if severity == "pass":
                severity = "warn"

    # RL-005: Stock-type fund is OK (we allow stock FUNDS, not individual stocks)
    # No rejection needed — stock funds are within our scope.

    return AuditResult(
        fund_code=fund.code,
        passed=(severity == "pass"),
        severity=severity,
        reasons=tuple(reasons),
    )
