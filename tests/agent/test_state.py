"""Tests for ConversationState schema."""
import pytest

from src.agent.state import ConversationState, create_initial_state


class TestConversationState:
    def test_create_initial_state_has_required_keys(self):
        state = create_initial_state(path="A", user_message="test")
        assert state["path"] == "A"
        assert state["user_message"] == "test"
        assert state["errors"] == []

    def test_default_values_are_none(self):
        state = create_initial_state(path="B", user_message="hello")
        assert state["risk_profile"] is None
        assert state["allocation_plan"] is None
        assert state["report_html"] is None

    def test_state_is_mutable_dict(self):
        state = create_initial_state(path="C", user_message="diagnose")
        state["risk_profile"] = "mock_profile"  # type: ignore
        assert state["risk_profile"] == "mock_profile"

    def test_all_three_paths_accepted(self):
        for p in ("A", "B", "C"):
            state = create_initial_state(path=p, user_message="test")
            assert state["path"] == p

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError, match="path"):
            create_initial_state(path="X", user_message="bad")
