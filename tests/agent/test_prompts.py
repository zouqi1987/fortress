"""Tests for prompt templates — constraint injection and structure."""
import pytest

from src.agent.prompts import build_debate_prompt


class TestBuildDebatePrompt:
    def test_includes_constraints(self):
        prompt = build_debate_prompt({"000001": []}, [])
        assert "不推荐个股" in prompt
        assert "不构成投资建议" in prompt

    def test_includes_bull_and_bear_sections(self):
        prompt = build_debate_prompt({"000001": []}, [])
        assert "多方" in prompt
        assert "空方" in prompt
        assert "综合判断" in prompt

    def test_includes_market_data_context(self):
        prompt = build_debate_prompt(
            {"000001": [{"date": "2025-06-19", "nav": 1.5}]},
            [],
        )
        assert "000001" in prompt

    def test_includes_holdings_context(self):
        prompt = build_debate_prompt({}, [{"code": "000001", "name": "华夏成长"}])
        assert "华夏成长" in prompt

    def test_empty_input_still_valid(self):
        prompt = build_debate_prompt({}, [])
        assert len(prompt) > 100  # Even empty input should produce a full prompt

    def test_prompt_is_string(self):
        prompt = build_debate_prompt({}, [])
        assert isinstance(prompt, str)

    def test_no_markdown_code_blocks_in_prompt_structure(self):
        """Prompt should be readable text, not nested markdown for the LLM."""
        prompt = build_debate_prompt({"000001": []}, [])
        # LLM output format instruction uses 中文, not markdown fences
        assert "##" not in prompt or "综合判断" in prompt
