"""LangGraph DAG definition — routes user intent to the correct pipeline.

Three paths:
  A (底仓配置): data_collector → allocator → risk_assessor → reporter
  B (机会捕捉): data_collector → debater → allocator → risk_assessor → reporter
  C (持仓诊断): data_collector → risk_assessor → reporter
"""
from langgraph.graph import END, StateGraph

from src.agent.nodes.allocator import allocator_node
from src.agent.nodes.data_collector import data_collector_node
from src.agent.nodes.debater import debater_node
from src.agent.nodes.reporter import reporter_node
from src.agent.nodes.risk_assessor import risk_assessor_node
from src.agent.state import ConversationState


def build_graph() -> StateGraph:
    """Construct and compile the fortress agent DAG.

    Returns a compiled LangGraph ready for .invoke() or .stream().
    """
    builder = StateGraph(ConversationState)

    # Register nodes
    builder.add_node("data_collector", data_collector_node)
    builder.add_node("debater", debater_node)
    builder.add_node("allocator", allocator_node)
    builder.add_node("risk_assessor", risk_assessor_node)
    builder.add_node("reporter", reporter_node)

    # Set entry point
    builder.set_entry_point("data_collector")

    # Conditional routing after data_collector based on path
    builder.add_conditional_edges(
        "data_collector",
        _route_after_collect,
        {
            "debater": "debater",
            "allocator": "allocator",
            "risk_assessor": "risk_assessor",
        },
    )

    # debater → allocator (Path B only, then continues like Path A)
    builder.add_edge("debater", "allocator")

    # allocator → risk_assessor
    builder.add_edge("allocator", "risk_assessor")

    # risk_assessor → reporter
    builder.add_edge("risk_assessor", "reporter")

    # reporter → END
    builder.add_edge("reporter", END)

    return builder.compile()


def _route_after_collect(state: ConversationState) -> str:
    """Determine next node based on the conversation path.

    Path A: → allocator (skip debate)
    Path B: → debater (bull/bear analysis first)
    Path C: → risk_assessor (skip allocation debate)
    """
    path = state.get("path", "A")

    if path == "B":
        return "debater"
    elif path == "C":
        return "risk_assessor"
    else:
        return "allocator"  # Path A default
