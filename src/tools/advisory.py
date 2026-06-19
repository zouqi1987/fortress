"""MCP tool: investment advisory."""
from decimal import Decimal

from src.agent.graph import build_graph
from src.agent.state import create_initial_state


def get_advice(path: str, message: str, portfolio: dict | None = None) -> dict:
    """Run the full advisory pipeline and return a report.

    Args:
        path: "A" (底仓配置), "B" (机会捕捉), or "C" (持仓诊断)
        message: user's question or context
        portfolio: optional {"equity": float, "bond": float, "cash": float}

    Returns:
        dict with report_html, path, and errors.
    """
    state = create_initial_state(path, message)

    if portfolio:
        try:
            validated = {
                k: Decimal(str(v))
                for k, v in portfolio.items()
            }
            state["portfolio"] = validated
        except (ValueError, TypeError, AttributeError) as e:
            return {
                "report_html": "",
                "path": path,
                "errors": [f"Invalid portfolio values: {e}"],
            }

    graph = build_graph()
    result = graph.invoke(state)

    return {
        "report_html": result.get("report_html", ""),
        "path": result.get("path"),
        "errors": result.get("errors", []),
    }
