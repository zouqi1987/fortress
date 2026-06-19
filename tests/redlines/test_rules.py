"""Tests for the redline rules DSL and rule sets."""
from datetime import date
from decimal import Decimal

import pytest

from src.datatypes import FundInfo
from src.redlines.hard_rules import HARD_RULES, RedLine, Severity, evaluate_rules
from src.redlines.personal_rules import PersonalRule, PersonalRuleSet


class TestRedLine:
    def test_rule_has_id_severity_and_condition(self):
        rule = RedLine(
            id="RL-TEST",
            severity=Severity.WARN,
            condition=lambda f, amount, total: amount > Decimal("10000"),
            message="test rule",
        )
        assert rule.id == "RL-TEST"
        assert rule.severity == Severity.WARN

    def test_evaluate_returns_violation_on_match(self):
        rule = RedLine(
            id="RL-001",
            severity=Severity.REJECT,
            condition=lambda f, amount, total: f.net_asset_value < Decimal("200_000_000"),
            message="fund too small",
        )
        fund = FundInfo("000001", "test", "mixed", Decimal("100_000_000"), Decimal("0.01"), date(2020, 1, 1))
        results = evaluate_rules([rule], fund, Decimal("50000"), Decimal("100000"))
        assert len(results) == 1
        assert results[0].rule_id == "RL-001"
        assert results[0].severity == Severity.REJECT

    def test_evaluate_returns_empty_on_no_match(self):
        rule = RedLine(
            id="RL-001",
            severity=Severity.REJECT,
            condition=lambda f, amount, total: False,
            message="never trigger",
        )
        fund = FundInfo("000001", "test", "mixed", Decimal("100_000_000"), Decimal("0.01"), date(2020, 1, 1))
        results = evaluate_rules([rule], fund, Decimal("50000"), Decimal("100000"))
        assert len(results) == 0


class TestHardRules:
    def test_all_hard_rules_have_unique_ids(self):
        ids = [r.id for r in HARD_RULES]
        assert len(ids) == len(set(ids))

    def test_hard_rules_cover_minimum_scenarios(self):
        assert len(HARD_RULES) >= 4  # size, age, fee, concentration


class TestPersonalRuleSet:
    def test_add_and_remove_rules(self):
        rules = PersonalRuleSet()
        rule = PersonalRule(
            id="PREF-001",
            description="avoid stock funds",
            fund_types_blacklist={"stock"},
        )
        rules.add(rule)
        assert len(rules.active) == 1

        rules.remove("PREF-001")
        assert len(rules.active) == 0

    def test_is_blacklisted(self):
        rules = PersonalRuleSet()
        rules.add(PersonalRule(
            id="PREF-001",
            description="no stock funds",
            fund_types_blacklist={"stock"},
        ))
        assert rules.is_blacklisted("stock")
        assert not rules.is_blacklisted("bond")

    def test_max_single_position(self):
        rules = PersonalRuleSet()
        rules.add(PersonalRule(
            id="PREF-002",
            description="max 10万 per fund",
            max_single_position=Decimal("100000"),
        ))
        assert rules.check_position_limit(Decimal("150000")) is False
        assert rules.check_position_limit(Decimal("50000")) is True

    def test_default_ruleset_is_empty(self):
        rules = PersonalRuleSet()
        assert len(rules.active) == 0
