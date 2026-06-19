"""Personal redline rules — user-configurable preferences.

Users can add/remove/modify these via conversation.
Each rule is a PersonalRule with type-specific constraints.
"""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class PersonalRule:
    """A user-defined preference rule."""

    id: str
    description: str = ""
    fund_types_blacklist: frozenset[str] = field(default_factory=frozenset)
    max_single_position: Decimal | None = None  # max per fund in CNY
    min_fund_size: Decimal | None = None  # user's minimum fund size


class PersonalRuleSet:
    """Collection of active personal rules."""

    def __init__(self) -> None:
        self._rules: dict[str, PersonalRule] = {}

    @property
    def active(self) -> list[PersonalRule]:
        return list(self._rules.values())

    def add(self, rule: PersonalRule) -> None:
        self._rules[rule.id] = rule

    def remove(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def is_blacklisted(self, fund_type: str) -> bool:
        """Check if a fund type is blacklisted by any active rule."""
        for rule in self._rules.values():
            if fund_type in rule.fund_types_blacklist:
                return True
        return False

    def check_position_limit(self, amount: Decimal) -> bool:
        """Check if amount exceeds any position limit. True = passes all limits."""
        for rule in self._rules.values():
            if rule.max_single_position is not None and amount > rule.max_single_position:
                return False
        return True

    def clear(self) -> None:
        self._rules.clear()
