"""Integration tests for LLM adapter and debater pipeline.

Tests debater node signal extraction (no external API needed).
Standalone LLM mode tests require FORTRESS_LLM + DEEPSEEK_API_KEY.
"""
import os

import pytest

from src.agent.llm import call_llm
from src.agent.nodes.debater import debater_node
from src.agent.state import create_initial_state

pytestmark = pytest.mark.integration


class TestDebaterE2E:
    def test_debater_extracts_signals(self):
        """Debater node extracts structured signals from market data."""
        state = create_initial_state("B", "test")
        state["market_data"] = {"000001": [{"date": "2026-06-19", "nav": 1.5, "pe": 12}]}
        state["holdings"] = [{"code": "000001", "name": "华夏成长"}]
        result = debater_node(state)
        debate = result.get("debate_result", "")
        assert len(debate) > 100
        assert "多方信号" in debate or "空方信号" in debate

    def test_debater_no_market_data(self):
        """Without market_data, debater returns error."""
        state = create_initial_state("B", "test")
        result = debater_node(state)
        assert "errors" in result


class TestStandaloneLLM:
    @pytest.mark.skipif(
        not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("FORTRESS_LLM"),
        reason="DEEPSEEK_API_KEY + FORTRESS_LLM not set",
    )
    def test_deepseek_call_real(self):
        """E2E: real DeepSeek API call in standalone mode."""
        result = call_llm("say hello in Chinese")
        assert len(result) > 10
