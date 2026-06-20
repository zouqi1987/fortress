"""Tests for macro overlay — regime detection and multiplier."""
from decimal import Decimal

import pytest

from src.engine.macro_overlay import MarketRegime, detect_regime, get_multiplier
from src.engine.risk_profile import RiskLevel


class TestDetectRegime:
    def test_returns_valid_regime(self):
        regime = detect_regime()
        assert regime in (MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS)

    def test_bull_when_price_above_ma(self):
        regime = detect_regime(current=3500, ma200=3000, ma120=3100)
        assert regime == MarketRegime.BULL

    def test_bear_when_price_below_ma120(self):
        regime = detect_regime(current=2800, ma200=3000, ma120=3100)
        assert regime == MarketRegime.BEAR

    def test_sideways_between_mas(self):
        # MA200 > current > MA120 = sideways
        regime = detect_regime(current=3050, ma200=3100, ma120=3000)
        assert regime == MarketRegime.SIDEWAYS

    def test_default_sideways_on_missing_data(self):
        regime = detect_regime(current=None)
        assert regime == MarketRegime.SIDEWAYS


class TestGetMultiplier:
    def test_bull_multiplier(self):
        m = get_multiplier(MarketRegime.BULL, RiskLevel.MODERATE)
        assert m == Decimal("1.0")

    def test_bear_conservative_is_less_impacted(self):
        m_bear = get_multiplier(MarketRegime.BEAR, RiskLevel.CONSERVATIVE)
        m_bull = get_multiplier(MarketRegime.BULL, RiskLevel.CONSERVATIVE)
        assert m_bear < m_bull  # bear always reduces

    def test_aggressive_bear_penalized_more(self):
        """Aggressive investors should reduce more in bear markets."""
        m_cons = get_multiplier(MarketRegime.BEAR, RiskLevel.CONSERVATIVE)
        m_aggr = get_multiplier(MarketRegime.BEAR, RiskLevel.AGGRESSIVE)
        assert m_aggr <= m_cons  # aggressive penalized equally or more

    def test_returns_decimal(self):
        for regime in MarketRegime:
            for level in RiskLevel:
                m = get_multiplier(regime, level)
                assert isinstance(m, Decimal)
                assert Decimal("0") < m <= Decimal("1.0")
