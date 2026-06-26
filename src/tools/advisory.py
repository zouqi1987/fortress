"""MCP tool: investment advisory."""
from decimal import Decimal

from src.agent.graph import build_graph
from src.agent.state import create_initial_state


def get_advice(path: str, message: str, portfolio: dict | None = None, num_holdings: int = 0) -> dict:
    """Run the full advisory pipeline and return a report.

    Args:
        path: "A" (底仓配置), "B" (机会捕捉), or "C" (持仓诊断)
        message: user's question or context
        portfolio: optional {"equity": float, "bond": float, "cash": float}
        num_holdings: number of fund holdings (drives diversification score).
            When > 0, sets a placeholder holdings list on state so downstream
            nodes (risk_assessor, debater) compute the correct count.

    Returns:
        dict with report_html, path, and errors.
    """
    state = create_initial_state(path, message)

    if num_holdings > 0:
        # All downstream consumers use len(holdings), not element contents,
        # so a placeholder list of the right length is sufficient and honest
        # about "we know the count, not the details".
        state["holdings"] = [None] * num_holdings

    if portfolio:
        try:
            validated = {
                k: Decimal(str(v))
                for k, v in portfolio.items()
            }
            state["portfolio"] = validated
        except (ValueError, TypeError, AttributeError, ArithmeticError) as e:
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


# ── Named Agent wrappers (thin wrappers, zero new logic) ──────────────


def allocate_portfolio(message: str, equity: float = 0, bond: float = 0, cash: float = 0, num_holdings: int = 0) -> dict:
    """Path A (底仓配置): risk profile → allocation → stress test → HTML report."""
    portfolio = {"equity": equity, "bond": bond, "cash": cash} if equity or bond or cash else None
    return get_advice("A", message, portfolio, num_holdings=num_holdings)


def hunt_opportunity(message: str, equity: float = 0, bond: float = 0, cash: float = 0, num_holdings: int = 0) -> dict:
    """Path B (机会捕捉): regime → debate → screening → allocation → HTML report."""
    portfolio = {"equity": equity, "bond": bond, "cash": cash} if equity or bond or cash else None
    return get_advice("B", message, portfolio, num_holdings=num_holdings)


def diagnose_holdings(message: str, equity: float = 0, bond: float = 0, cash: float = 0, num_holdings: int = 0) -> dict:
    """Path C (持仓诊断): health check → audit → stress test → HTML report."""
    portfolio = {"equity": equity, "bond": bond, "cash": cash} if equity or bond or cash else None
    return get_advice("C", message, portfolio, num_holdings=num_holdings)
