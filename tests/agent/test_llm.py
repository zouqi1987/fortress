"""Tests for LLM client — API call with graceful degradation."""
import os
from unittest import mock

import pytest

from src.agent.llm import call_llm


@pytest.fixture(autouse=True)
def set_api_key():
    """Ensure ANTHROPIC_API_KEY is set for all tests in this module."""
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        yield


class TestCallLLM:
    def test_returns_text_on_success(self):
        with mock.patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value.content = [
                mock.MagicMock(text="分析结果：多方占优")
            ]
            result = call_llm("test prompt")
            assert result == "分析结果：多方占优"

    def test_passes_model_and_max_tokens(self):
        with mock.patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value.content = [
                mock.MagicMock(text="ok")
            ]
            call_llm("test")
            call_args = mock_client.return_value.messages.create.call_args
            kwargs = call_args[1]
            assert "model" in kwargs
            assert kwargs["max_tokens"] > 0
            assert kwargs["messages"][0]["content"] == "test"

    def test_graceful_degradation_on_api_error(self):
        with mock.patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.side_effect = Exception("API unavailable")
            result = call_llm("test prompt")
            assert "暂时不可用" in result

    def test_returns_text_on_key_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = call_llm("test")
            assert len(result) > 100
            assert "多空辩论" in result

    def test_respects_max_tokens(self):
        with mock.patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value.content = [
                mock.MagicMock(text="short")
            ]
            call_llm("prompt", max_tokens=500)
            kwargs = mock_client.return_value.messages.create.call_args[1]
            assert kwargs["max_tokens"] <= 500
