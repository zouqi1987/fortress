"""Conversation state schema for the fortress agent LangGraph DAG.

TypedDict — zero dependencies, works with LangGraph's state management.
"""
from typing import NotRequired, TypedDict


class ConversationState(TypedDict):
    """Full conversation context flowing through the agent DAG."""

    # ── User input ───────────────────────────────────────────────────
    path: str  # "A" | "B" | "C"
    user_message: str

    # ── Collected data (populated by data_collector node) ────────────
    risk_profile: NotRequired[object]  # RiskProfile from engine
    portfolio: NotRequired[dict[str, object]]  # {"equity": D, "bond": D, "cash": D}
    market_data: NotRequired[dict[str, object]]  # code → NAVPoint[]
    holdings: NotRequired[list[object]]  # current positions

    # ── Analysis results ─────────────────────────────────────────────
    debate_result: NotRequired[str]  # Bull/Bear summary (path B only)
    allocation_plan: NotRequired[object]  # AllocationPlan
    audit_results: NotRequired[list[object]]  # list[AuditResult]
    stress_result: NotRequired[object]  # StressResult
    health_check: NotRequired[object]  # HealthCheckResult

    # ── Output ───────────────────────────────────────────────────────
    report_html: NotRequired[str]

    # ── Error tracking ───────────────────────────────────────────────
    errors: list[str]


_VALID_PATHS = {"A", "B", "C"}


def create_initial_state(path: str, user_message: str) -> ConversationState:
    """Create a fresh state for a new conversation turn.

    Args:
        path: "A" (底仓配置), "B" (机会捕捉), or "C" (持仓诊断).
        user_message: Raw user input text.

    Returns:
        Initialized ConversationState with all optional fields unset.

    Raises:
        ValueError: if path is not one of A/B/C.
    """
    if path not in _VALID_PATHS:
        raise ValueError(f"path must be one of {_VALID_PATHS}, got {path!r}")

    return ConversationState(
        path=path,
        user_message=user_message,
        risk_profile=None,
        portfolio=None,
        market_data=None,
        holdings=None,
        debate_result=None,
        allocation_plan=None,
        audit_results=None,
        stress_result=None,
        health_check=None,
        report_html=None,
        errors=[],
    )
