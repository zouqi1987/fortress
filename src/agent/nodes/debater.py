"""Debater node — Bull vs Bear market opportunity analysis via LLM.

Pure function: (state) → state_update dict.
Only active on path B (机会捕捉).
"""
from src.agent.llm import call_llm
from src.agent.prompts import build_debate_prompt
from src.agent.state import ConversationState


def debater_node(state: ConversationState) -> dict:
    """Generate Bull vs Bear debate analysis via LLM.

    Requires market_data in state. Falls back to structured text if LLM unavailable.
    """
    market_data = state.get("market_data")

    if not market_data:
        return {
            "errors": state.get("errors", []) + ["debater: no market data to analyze"],
        }

    holdings = state.get("holdings") or []
    prompt = build_debate_prompt(market_data, holdings)
    debate = call_llm(prompt)

    return {"debate_result": debate}
