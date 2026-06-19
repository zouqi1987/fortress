"""Debater node — Bull vs Bear market opportunity analysis.

Pure function: (state) → state_update dict.
Only active on path B (机会捕捉).
"""
from src.agent.state import ConversationState


def debater_node(state: ConversationState) -> dict:
    """Generate Bull vs Bear debate analysis.

    Requires market_data in state. Returns debate_result or errors.
    """
    market_data = state.get("market_data")

    if not market_data:
        return {
            "errors": state.get("errors", []) + ["debater: no market data to analyze"],
        }

    # Generate structured debate (placeholder — real impl calls LLM)
    num_funds = len(market_data)
    bull_points = [
        "市场估值处于合理区间",
        f"已覆盖 {num_funds} 只基金的基本面数据",
        "政策面释放积极信号",
    ]
    bear_points = [
        "短期波动率上升，需警惕回调风险",
        "行业轮动加速，单一策略难以持续获利",
        "外部宏观不确定性仍存",
    ]

    debate = (
        "## 多空辩论\n\n"
        "### 🟢 多方观点\n"
        + "".join(f"- {p}\n" for p in bull_points)
        + "\n### 🔴 空方观点\n"
        + "".join(f"- {p}\n" for p in bear_points)
        + "\n### ⚖️ 综合判断\n"
        + "多方因素略占优，建议谨慎参与，控制仓位不超过组合的15%。"
    )

    return {"debate_result": debate}
