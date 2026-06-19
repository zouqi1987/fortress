"""Integration test for real Claude API call via debater pipeline.

Requires ANTHROPIC_API_KEY — skipped/xfailed otherwise.
Run: ANTHROPIC_API_KEY=sk-... pytest tests/integration/test_llm_integration.py -v
"""
import os

import pytest

from src.agent.llm import call_llm
from src.agent.nodes.debater import debater_node
from src.agent.prompts import build_debate_prompt
from src.agent.state import create_initial_state

pytestmark = pytest.mark.integration

needs_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


class TestLiveClaudeCall:
    @needs_api_key
    def test_call_llm_real(self):
        """E2E: real Claude API call returns structured debate."""
        prompt = build_debate_prompt({"000001": []}, [])
        result = call_llm(prompt)
        assert "多方" in result
        assert "空方" in result
        assert len(result) > 200

    @needs_api_key
    def test_debater_node_real(self):
        """E2E: debater node through full pipeline."""
        state = create_initial_state("B", "test market opportunity")
        state["market_data"] = {"000001": [{"date": "2026-06-19", "nav": 1.5}]}
        state["holdings"] = [{"code": "000001", "name": "华夏成长"}]

        result = debater_node(state)
        debate = result.get("debate_result", "")
        assert len(debate) > 100
        assert "多方" in debate or "bull" in debate.lower()

    def test_debater_fallback_no_key(self):
        """Without API key, debater returns fallback analysis (not error)."""
        # This test works because no API key = fallback behavior
        state = create_initial_state("B", "test")
        state["market_data"] = {"000001": []}
        result = debater_node(state)
        debate = result.get("debate_result", "")
        assert len(debate) > 100
        assert "多空辩论" in debate
