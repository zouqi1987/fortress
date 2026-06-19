"""Prompt templates for LLM-powered agent nodes.

All prompts inject mandatory constraints: no stock tips, no trading, disclaimer.
"""
import json


def build_debate_prompt(
    market_data: dict[str, list],
    holdings: list[dict],
) -> str:
    """Build the Bull vs Bear debate prompt with market context and constraints.

    Args:
        market_data: fund_code → list of NAV/index data dicts.
        holdings: list of current position dicts.

    Returns:
        A complete prompt string for the LLM.
    """
    context_parts: list[str] = []

    # Market data summary
    if market_data:
        context_parts.append(f"关注基金: {', '.join(market_data.keys())}")
        context_parts.append(f"数据点: {sum(len(v) for v in market_data.values())} 条")

    # Holdings context
    if holdings:
        h_names = [h.get("name", h.get("code", "?")) for h in holdings]
        context_parts.append(f"当前持仓: {', '.join(h_names)}")

    context = "\n".join(context_parts) if context_parts else "无特定市场数据"

    return f"""你是一位专业的基金投资分析师。请基于以下市场数据进行多空辩论分析。

## 市场背景
{context}

## 分析要求
请从多方（看涨）和空方（看跌）两个角度进行分析，每个角度至少列出 3 个论点。
最后给出综合判断。

## 输出格式
### 🟢 多方观点
- 论点1
- 论点2
- 论点3

### 🔴 空方观点
- 论点1
- 论点2
- 论点3

### ⚖️ 综合判断
（一段综合分析，含仓位建议）

## 重要约束
- 不推荐个股，仅分析基金/ETF
- 不构成投资建议
- 不触发任何交易操作
- 如有不确定性，明确告知"""
