"""LLM client wrapper — calls Claude API with graceful degradation.

Reads ANTHROPIC_API_KEY from environment. Falls back to local analysis
if the API is unavailable or the module is not installed.
"""
import os


def call_llm(prompt: str, max_tokens: int = 1024) -> str:
    """Call the Claude API with a prompt. Falls back gracefully on any error.

    Args:
        prompt: The complete prompt string to send.
        max_tokens: Maximum tokens in the response.

    Returns:
        LLM response text, or a fallback message if unavailable.
    """
    # Try to import and call the Anthropic SDK
    try:
        import anthropic
    except ImportError:
        return _fallback_response("Anthropic SDK 未安装")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_response("ANTHROPIC_API_KEY 未设置")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from the first content block
        if message.content and len(message.content) > 0:
            return str(message.content[0].text)
        return _fallback_response("API 返回空内容")

    except Exception:
        return _fallback_response("API 调用失败")


def _fallback_response(reason: str) -> str:
    """Generate a safe fallback analysis when the LLM is unavailable."""
    return f"""## 多空辩论

> ⚠️ AI 分析暂时不可用 ({reason})

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
重点关注持仓基金的季报披露和费率变化。

*免责声明: 本分析不构成投资建议。*"""
