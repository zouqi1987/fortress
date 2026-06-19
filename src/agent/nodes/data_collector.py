"""Data collector node — fetches portfolio and market data.

Pure function: (state) → state_update dict.
TODO(Phase 8): Inject real portfolio_db/market data via dependency injection.
Currently returns static defaults safe for demo/testing.
"""
from src.agent.state import ConversationState


def data_collector_node(state: ConversationState) -> dict:
    """Fetch portfolio positions and relevant market data.

    In production, the data layer callables are injected via factory.
    For now, returns a safe default — callers can override with real data.
    """
    updates: dict = {}

    # Portfolio placeholder — real implementation injects portfolio_db
    updates["portfolio"] = state.get("portfolio") or {
        "equity": 0,
        "bond": 0,
        "cash": 0,
    }

    # Market data placeholder
    updates["market_data"] = state.get("market_data") or {}

    # Holdings placeholder
    updates["holdings"] = state.get("holdings") or []

    return updates
