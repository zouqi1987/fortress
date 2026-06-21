"""Unit tests for named agent wrappers — verify path routing and registry integrity."""
import pytest

from src.tools.advisory_agents import AGENT_REGISTRY, AgentMeta, get_agent, list_agents


class TestAgentRegistry:
    """Registry integrity — metadata is complete and consistent."""

    def test_three_agents_registered(self):
        assert len(AGENT_REGISTRY) == 3

    def test_every_agent_has_valid_path(self):
        for agent in AGENT_REGISTRY:
            assert agent.path in ("A", "B", "C"), f"{agent.name} path={agent.path!r}"

    def test_names_are_unique(self):
        names = [a.name for a in AGENT_REGISTRY]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_paths_are_unique(self):
        paths = [a.path for a in AGENT_REGISTRY]
        assert len(paths) == len(set(paths)), f"Duplicate paths: {paths}"

    def test_descriptions_are_non_empty_and_non_whitespace(self):
        """Descriptions must be non-empty and not start with whitespace."""
        for agent in AGENT_REGISTRY:
            assert len(agent.description) > 10, f"{agent.name} description too short"
            assert agent.description[0] != " ", f"{agent.name} description starts with space"


class TestAgentLookup:
    """Lookup functions — correct by-name retrieval."""

    def test_get_agent_finds_each_by_name(self):
        for agent in AGENT_REGISTRY:
            found = get_agent(agent.name)
            assert found is not None, f"{agent.name} not found"
            assert found.path == agent.path

    def test_get_agent_returns_none_for_unknown(self):
        assert get_agent("不存在的 Agent") is None
        assert get_agent("") is None

    def test_list_agents_returns_all(self):
        agents = list_agents()
        assert len(agents) == 3

    def test_list_agents_returns_same_order_as_registry(self):
        agents = list_agents()
        for i, agent in enumerate(agents):
            assert agent.name == AGENT_REGISTRY[i].name


class TestAgentPaths:
    """Path mapping — each agent maps to a distinct DAG path."""

    def test_a_is_allocate(self):
        a = get_agent("底仓配置")
        assert a.path == "A"

    def test_b_is_hunt(self):
        b = get_agent("机会捕捉")
        assert b.path == "B"

    def test_c_is_diagnose(self):
        c = get_agent("持仓诊断")
        assert c.path == "C"


class TestAgentMetaintegrity:
    """AgentMeta dataclass — frozen and well-formed."""

    def test_agent_meta_is_frozen(self):
        agent = AGENT_REGISTRY[0]
        with pytest.raises(Exception):  # FrozenInstanceError, AttributeError, etc
            agent.name = "changed"  # type: ignore[misc]

    def test_all_fields_present(self):
        agent = AGENT_REGISTRY[0]
        assert hasattr(agent, "name")
        assert hasattr(agent, "path")
        assert hasattr(agent, "description")
