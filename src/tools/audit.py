"""MCP tool: fund audit."""
from datetime import date
from decimal import Decimal

from src.datatypes import FundInfo
from src.engine.auditor import audit_fund


def audit_single_fund(
    code: str,
    name: str,
    fund_type: str,
    net_asset_value: float,
    fee_rate: float,
    inception_date: str,
    planned_amount: float,
    total_portfolio: float | None = None,
) -> dict:
    """Audit a single fund against redline rules.

    Args:
        code: fund code
        name: fund name
        fund_type: "stock"|"bond"|"mixed"|"index"|"money"
        net_asset_value: fund size in CNY
        fee_rate: annual fee (e.g. 0.015 = 1.5%)
        inception_date: "YYYY-MM-DD"
        planned_amount: planned investment in CNY
        total_portfolio: total portfolio value for concentration check
    """
    fund = FundInfo(
        code=code,
        name=name,
        type=fund_type,
        net_asset_value=Decimal(str(net_asset_value)),
        fee_rate=Decimal(str(fee_rate)),
        inception_date=date.fromisoformat(inception_date),
    )

    total = Decimal(str(total_portfolio)) if total_portfolio is not None else None
    result = audit_fund(fund, Decimal(str(planned_amount)), total)

    return {
        "fund_code": result.fund_code,
        "passed": result.passed,
        "severity": result.severity,
        "reasons": list(result.reasons),
    }
