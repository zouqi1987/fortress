"""Tests for optional standalone LLM adapter."""
import os
from unittest import mock

from src.agent.llm import call_llm


class TestCallLLMFallback:
    """Without FORTRESS_LLM set, call_llm returns fallback (Skill mode)."""

    def test_fallback_without_provider(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = call_llm("test")
            assert "独立模式未启用" in result

    def test_fallback_on_unknown_provider(self):
        with mock.patch.dict(os.environ, {"FORTRESS_LLM": "openai"}, clear=True):
            result = call_llm("test")
            assert "不支持" in result

    def test_deepseek_without_key(self):
        with mock.patch.dict(os.environ, {"FORTRESS_LLM": "deepseek"}, clear=True):
            result = call_llm("test")
            assert "API_KEY 未设置" in result or "pending" in result


class TestCallLLMWithKey:
    """DeepSeek mode with API key set — placeholder returns pending."""

    def test_deepseek_with_key(self):
        with mock.patch.dict(os.environ, {
            "FORTRESS_LLM": "deepseek",
            "DEEPSEEK_API_KEY": "sk-test",
        }, clear=True):
            result = call_llm("test")
            assert "pending" in result.lower()
