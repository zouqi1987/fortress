"""Hard redline rules — universal, cannot be disabled by users.

Declarative DSL: each rule is a RedLine with id, severity, condition, and message.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Callable

from src.datatypes import FundInfo


class Severity(Enum):
    WARN = "warn"
    REJECT = "reject"


@dataclass(frozen=True)
class RedLine:
    """A single hard redline rule.

    condition receives (fund, planned_amount, total_portfolio) and returns bool.
    True = rule triggered (violation).
    """

    id: str
    severity: Severity
    condition: Callable[[FundInfo, Decimal, Decimal | None], bool]
    message: str


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    severity: Severity
    message: str


def evaluate_rules(
    rules: list[RedLine],
    fund: FundInfo,
    planned_amount: Decimal,
    total_portfolio: Decimal | None = None,
) -> list[RuleViolation]:
    """Evaluate a set of rules against a fund + planned position.

    Returns all triggered violations. Empty list = all pass.
    """
    violations: list[RuleViolation] = []
    for rule in rules:
        try:
            if rule.condition(fund, planned_amount, total_portfolio):
                violations.append(
                    RuleViolation(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=rule.message,
                    )
                )
        except Exception:
            # Rule evaluation should never crash — skip broken rules
            pass
    return violations


# ── Hard Rules ───────────────────────────────────────────────────────

HARD_RULES: list[RedLine] = [
    RedLine(
        id="RL-001",
        severity=Severity.REJECT,
        condition=lambda f, amount, total: (
            f.net_asset_value < Decimal("200_000_000")
            and amount > Decimal("50_000")
        ),
        message="基金规模 < 2亿，单客户持仓不得超过 5万元",
    ),
    RedLine(
        id="RL-002",
        severity=Severity.WARN,
        condition=lambda f, amount, total: (
            (date.today() - f.inception_date).days < 365
        ),
        message="基金成立不足1年，缺乏足够历史业绩验证",
    ),
    RedLine(
        id="RL-003",
        severity=Severity.WARN,
        condition=lambda f, amount, total: f.fee_rate > Decimal("0.015"),
        message="管理费率超过 1.5%，侵蚀长期收益",
    ),
    RedLine(
        id="RL-004",
        severity=Severity.WARN,
        condition=lambda f, amount, total: (
            total is not None
            and total > Decimal("0")
            and amount / total > Decimal("0.20")
        ),
        message="单只基金占组合比例超过 20%，集中度风险过高",
    ),
    RedLine(
        id="RL-005",
        severity=Severity.WARN,
        condition=lambda f, amount, total: (
            f.net_asset_value < Decimal("500_000_000")
            and amount > Decimal("20_000")
        ),
        message="基金规模 < 5亿，建议单客户持仓不超过 2万元",
    ),
]
