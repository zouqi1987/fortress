"""Agent metadata registry — maps user-facing agent names to DAG paths.

Mirrors the agent-plugin frontmatter pattern from claude-for-financial-services-cn
(e.g., china-model-builder → mcp__akshare__* + skills composed).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentMeta:
    """Metadata for a fortress advisory agent."""

    name: str          # User-facing Chinese name (MCP tool name)
    path: str          # DAG path ("A" | "B" | "C")
    description: str   # One-line purpose shown in tool listing


AGENT_REGISTRY: tuple[AgentMeta, ...] = (
    AgentMeta(
        name="底仓配置",
        path="A",
        description="风险测评 → 资产配置 → 压力测试。适合寻求确定性的用户首次建立投资组合。",
    ),
    AgentMeta(
        name="机会捕捉",
        path="B",
        description="市场周期研判 → 基金筛选 → 多空信号提取 → 配置建议。适合寻求收益的用户捕捉市场时机。",
    ),
    AgentMeta(
        name="持仓诊断",
        path="C",
        description="持仓健康检查 → 红线审计 → 压力测试。适合定期检查投资组合的风险和集中度。",
    ),
)


def get_agent(name: str) -> AgentMeta | None:
    """Look up an agent by its user-facing name."""
    for agent in AGENT_REGISTRY:
        if agent.name == name:
            return agent
    return None


def list_agents() -> list[AgentMeta]:
    """Return all registered agents."""
    return list(AGENT_REGISTRY)
