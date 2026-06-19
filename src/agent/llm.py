"""Optional standalone LLM adapter — for running fortress without a host agent.

Default mode: Host LLM (Claude Code / Hermes) calls MCP tools → fortress returns
structured signals → host LLM narrates in natural language. No API key needed.

Standalone mode: Set FORTRESS_LLM=deepseek + DEEPSEEK_API_KEY to have fortress
generate its own narrative text. Only needed when running without a host agent.
"""
import os


def call_llm(prompt: str, max_tokens: int = 1024) -> str:
    """Call external LLM API (optional, for standalone mode).

    In normal operation, fortress is a Skill embedded in Claude Code.
    The host LLM provides the natural language capability — fortress
    only provides structured signals. This function exists for standalone
    mode (e.g., running fortress as a CLI without a host agent).

    Set FORTRESS_LLM=deepseek to enable standalone mode.
    """
    llm_provider = os.environ.get("FORTRESS_LLM", "")

    if not llm_provider:
        return _fallback_response("独立模式未启用 — 堡垒作为 Skill 运行，宿主 LLM 负责语言生成")

    if llm_provider == "deepseek":
        return _call_deepseek(prompt, max_tokens)

    return _fallback_response(f"不支持的 LLM provider: {llm_provider}")


def _call_deepseek(prompt: str, max_tokens: int) -> str:
    """Call DeepSeek API in standalone mode."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return _fallback_response("DEEPSEEK_API_KEY 未设置")

    # Placeholder — implement when DeepSeek standalone mode is needed
    return _fallback_response("DeepSeek standalone mode — implementation pending")


def _fallback_response(reason: str) -> str:
    """Generate a safe fallback analysis when the LLM is unavailable."""
    return f"""## 多空辩论

> ⚠️ 自主 AI 分析未启用 ({reason})

### 🟢 多方观点
- 市场整体估值处于合理区间
- 政策面持续释放积极信号
- 长期定投策略可平滑短期波动

### 🔴 空方观点
- 短期市场波动率上升，需警惕回调风险
- 行业轮动加速，单一策略难以持续获利
- 外部宏观不确定性仍存

### ⚖️ 综合判断
基于当前可得数据，建议保持仓位不变，等待更明确的市场信号。

*免责声明: 本分析不构成投资建议。*"""
