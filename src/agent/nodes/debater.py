"""Debater node — Bull vs Bear signal extraction.

Pure function: (state) → state_update dict.
Only active on path B (机会捕捉).

Outputs structured signals that the host LLM (Claude Code) wraps into
natural language debate. Skill = compute engine. Host = narrator.
"""
from src.agent.signals import extract_signals
from src.agent.state import ConversationState


def debater_node(state: ConversationState) -> dict:
    """Extract debate signals from market data and holdings.

    Requires market_data in state. Outputs structured signals for the
    host LLM to render as natural language bull/bear debate.

    No external API calls. No API keys needed.
    """
    market_data = state.get("market_data")

    if not market_data:
        return {
            "errors": state.get("errors", []) + ["debater: no market data to analyze"],
            "debate_result": "",
        }

    holdings = state.get("holdings") or []
    signals = extract_signals(market_data, holdings)

    # Format as readable text for the host LLM to narrate
    parts = ["## 多空辩论信号\n"]

    parts.append("### 🟢 多方信号\n")
    for s in signals.bull_signals:
        parts.append(f"- **{s.name}**: {s.value} — {s.interpretation}")
    if not signals.bull_signals:
        parts.append("- （当前无显著多方信号）")

    parts.append("\n### 🔴 空方信号\n")
    for s in signals.bear_signals:
        parts.append(f"- **{s.name}**: {s.value} — {s.interpretation}")
    if not signals.bear_signals:
        parts.append("- （当前无显著空方信号）")

    parts.append(f"\n### ⚖️ {signals.conclusion_framework}")

    return {"debate_result": "\n".join(parts)}
