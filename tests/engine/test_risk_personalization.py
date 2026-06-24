"""Tests for risk personalization — fund-type classification + weight tables.

Zero I/O pure module: classify_fund_type maps fortress fund types to scoring
classes (active/passive/money); WEIGHTS holds 9 weight rows (3 fund-type
classes × 3 risk profiles) with dimension weights summing to 1.0.

Methodology basis:
- Active funds (bond/mixed/stock) — Morningstar Medalist active pillar weights
  (People 45% / Process 45% / Parent 10%) refracted into 5 dimensions with
  peer_performance scaling up for more aggressive profiles.
- Passive funds (index) — Morningstar Medalist passive pillar weights
  (People 10% / Process 80%) refracted with fee heavily weighted (tracking
  error and cost dominate passive fund selection).
- Money funds — only 3 dimensions (institutional_consensus / peer_performance /
  fee) because amortized-cost accounting eliminates volatility, so
  risk_control and persistence are structurally N/A.
"""
import pytest

from src.engine.risk_personalization import (
    WEIGHTS,
    classify_fund_type,
    get_weights,
)


class TestClassifyFundType:
    def test_bond_maps_to_active(self):
        """bond → active (actively-managed bond fund)."""
        assert classify_fund_type("bond") == "active"

    def test_mixed_maps_to_active(self):
        """mixed → active (actively-managed mixed/allocation fund)."""
        assert classify_fund_type("mixed") == "active"

    def test_stock_maps_to_active(self):
        """stock → active (actively-managed equity fund)."""
        assert classify_fund_type("stock") == "active"

    def test_index_maps_to_passive(self):
        """index → passive (tracks a benchmark, not actively managed)."""
        assert classify_fund_type("index") == "passive"

    def test_money_maps_to_money(self):
        """money → money (money market fund — special 3-dimension scoring)."""
        assert classify_fund_type("money") == "money"

    def test_unknown_type_raises_value_error(self):
        """Unrecognized fund_type → ValueError, not a silent fallback.

        Defense at boundary: a typo in fund_type must surface immediately,
        not silently score as some default class.
        """
        with pytest.raises(ValueError):
            classify_fund_type("unknown")

    def test_empty_string_raises_value_error(self):
        """Empty string → ValueError."""
        with pytest.raises(ValueError):
            classify_fund_type("")


class TestWeightsShape:
    @pytest.mark.parametrize(
        "fund_class,risk_level,expected_keys",
        [
            ("active", "conservative", 5),
            ("active", "moderate", 5),
            ("active", "aggressive", 5),
            ("passive", "conservative", 5),
            ("passive", "moderate", 5),
            ("passive", "aggressive", 5),
            ("money", "conservative", 3),
            ("money", "moderate", 3),
            ("money", "aggressive", 3),
        ],
    )
    def test_each_row_has_expected_key_count(
        self, fund_class, risk_level, expected_keys
    ):
        """Active/passive have 5 dimensions; money has 3 (no risk_control/persistence)."""
        row = WEIGHTS[fund_class][risk_level]
        assert len(row) == expected_keys
        if fund_class == "money":
            # Money funds structurally exclude these
            assert "risk_control" not in row
            assert "persistence" not in row
        else:
            # Active/passive must have all 5 dimensions
            for dim in (
                "institutional_consensus",
                "peer_performance",
                "risk_control",
                "persistence",
                "fee",
            ):
                assert dim in row, f"Missing dimension {dim} for {fund_class}/{risk_level}"

    @pytest.mark.parametrize(
        "fund_class,risk_level",
        [
            ("active", "conservative"),
            ("active", "moderate"),
            ("active", "aggressive"),
            ("passive", "conservative"),
            ("passive", "moderate"),
            ("passive", "aggressive"),
            ("money", "conservative"),
            ("money", "moderate"),
            ("money", "aggressive"),
        ],
    )
    def test_each_row_sums_to_one(self, fund_class, risk_level):
        """All 9 weight rows must sum to exactly 1.0 — no weight leaks."""
        row = WEIGHTS[fund_class][risk_level]
        assert sum(row.values()) == pytest.approx(1.0)


class TestWeightsSpecificValues:
    def test_active_congressive(self):
        """Sanity: active/conservative has the spec values."""
        row = WEIGHTS["active"]["conservative"]
        assert row["institutional_consensus"] == pytest.approx(0.25)
        assert row["peer_performance"] == pytest.approx(0.10)
        assert row["risk_control"] == pytest.approx(0.30)
        assert row["persistence"] == pytest.approx(0.15)
        assert row["fee"] == pytest.approx(0.20)

    def test_passive_aggressive_fee_is_0_50(self):
        """Acceptance criterion: passive/aggressive/fee == 0.50.

        Passive funds heaviest fee weight in aggressive profile — tracking
        error and cost dominate.
        """
        assert WEIGHTS["passive"]["aggressive"]["fee"] == pytest.approx(0.50)

    def test_money_moderate_keys(self):
        """Acceptance criterion: money/moderate has exactly 3 keys."""
        row = WEIGHTS["money"]["moderate"]
        assert set(row.keys()) == {
            "institutional_consensus",
            "peer_performance",
            "fee",
        }

    def test_money_moderate_values(self):
        """Sanity: money/moderate has the spec values."""
        row = WEIGHTS["money"]["moderate"]
        assert row["institutional_consensus"] == pytest.approx(0.35)
        assert row["peer_performance"] == pytest.approx(0.35)
        assert row["fee"] == pytest.approx(0.30)


class TestGetWeights:
    def test_active_conservative_returns_5_key_dict(self):
        """get_weights('active', 'conservative') returns the 5-key weight dict."""
        w = get_weights("active", "conservative")
        assert set(w.keys()) == {
            "institutional_consensus",
            "peer_performance",
            "risk_control",
            "persistence",
            "fee",
        }
        assert sum(w.values()) == pytest.approx(1.0)

    def test_money_moderate_returns_3_key_dict(self):
        """get_weights('money', 'moderate') returns the 3-key weight dict."""
        w = get_weights("money", "moderate")
        assert set(w.keys()) == {
            "institutional_consensus",
            "peer_performance",
            "fee",
        }

    def test_invalid_risk_level_raises_value_error(self):
        """Invalid risk_level → ValueError, not silent default."""
        with pytest.raises(ValueError):
            get_weights("active", "invalid")

    def test_invalid_fund_type_class_raises_value_error(self):
        """Invalid fund_type_class → ValueError, not silent default."""
        with pytest.raises(ValueError):
            get_weights("invalid", "conservative")

    def test_both_invalid_raises_value_error(self):
        """Both args invalid → ValueError (fund_type checked first)."""
        with pytest.raises(ValueError):
            get_weights("invalid", "invalid")

    def test_returns_same_object_as_weights_table(self):
        """get_weights returns the WEIGHTS dict entry — not a copy.

        Performance: weight tables are immutable in practice; avoid copy overhead.
        """
        w = get_weights("active", "conservative")
        assert w is WEIGHTS["active"]["conservative"]
