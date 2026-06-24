"""A2A (Agent-to-Agent) adapter for Hermes Agent and other A2A-compatible agents.

Two integration paths for fortress:

1. MCP (RECOMMENDED): Hermes has built-in MCP client support.
   Add fortress to ~/.hermes/config.yaml:
   ```yaml
   mcp_servers:
     fortress:
       command: /path/to/fortress/.venv/bin/python
       args: [-m, src.tools.server]
       env: {FORTRESS_DATA_DIR: /path/to/fortress/data}
       enabled: true
   ```

2. A2A (this module): For agents that use the A2A protocol natively.
   ```bash
   pip install a2a-sdk
   python -m src.tools.a2a_adapter
   ```

Status: MCP path PRODUCTION-READY. A2A path EXPERIMENTAL (SDK v1.1.0, API evolving).
"""
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Agent Card (A2A discovery document) ──────────────────────────────

AGENT_CARD: dict = {
    "name": "fortress",
    "description": "AI 投资顾问 — 对话式基金/ETF 组合管理",
    "version": "0.1.0",
    "capabilities": {"tasks": True, "streaming": False},
    "skills": [
        {
            "name": "assess_risk",
            "description": "6 因子风险测评 (A-E 统一问卷)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "horizon": {"type": "string", "description": "A(1年内)|B(1-2年)|C(2-3年)|D(3-5年)|E(5年以上)"},
                    "max_loss_pct": {"type": "number"},
                    "income": {"type": "integer", "minimum": 1, "maximum": 5},
                    "experience": {"type": "integer", "minimum": 1, "maximum": 5},
                    "liquidity": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["horizon", "max_loss_pct", "income", "experience", "liquidity"],
            },
        },
        {
            "name": "get_allocation",
            "description": "三层架构配置方案",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "risk_level": {"type": "string", "description": "conservative/moderate/aggressive"},
                    "total_amount": {"type": "number"},
                },
                "required": ["risk_level", "total_amount"],
            },
        },
        {
            "name": "get_advice",
            "description": "完整投顾报告（路径 A/B/C）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "A/B/C"},
                    "message": {"type": "string"},
                    "equity": {"type": "number"},
                    "bond": {"type": "number"},
                    "cash": {"type": "number"},
                },
                "required": ["path", "message"],
            },
        },
        {
            "name": "audit_single_fund",
            "description": "单品红线审计",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "name": {"type": "string"},
                    "fund_type": {"type": "string"},
                    "net_asset_value": {"type": "number"},
                    "fee_rate": {"type": "number"},
                    "inception_date": {"type": "string"},
                    "planned_amount": {"type": "number"},
                    "total_portfolio": {"type": "number"},
                },
                "required": ["code", "name", "fund_type", "net_asset_value", "fee_rate", "inception_date", "planned_amount"],
            },
        },
        {
            "name": "run_scenario",
            "description": "情景压力测试",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "equity": {"type": "number"},
                    "bond": {"type": "number"},
                    "cash": {"type": "number"},
                    "scenario_name": {"type": "string"},
                },
                "required": ["equity", "bond", "cash"],
            },
        },
        {
            "name": "lookup_fund",
            "description": "基金数据查询（三级降级，支持自定义日期区间）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "start": {"type": "string", "description": "YYYY-MM-DD (default: 30 days ago)"},
                    "end": {"type": "string", "description": "YYYY-MM-DD (default: today)"},
                },
                "required": ["code"],
            },
        },
        {
            "name": "lookup_index",
            "description": "指数日线数据查询（三级降级）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "e.g. 000001 for 上证指数"},
                    "start": {"type": "string", "description": "YYYY-MM-DD (default: 90 days ago)"},
                    "end": {"type": "string", "description": "YYYY-MM-DD (default: today)"},
                },
                "required": ["code"],
            },
        },
        {
            "name": "list_hard_rules",
            "description": "列出全部5条硬红线规则",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "check_health",
            "description": "四维度组合健康度评分",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "equity_pct": {"type": "integer"},
                    "bond_pct": {"type": "integer"},
                    "cash_pct": {"type": "integer"},
                    "risk_level": {"type": "string"},
                    "fee_ratio": {"type": "number"},
                    "max_drawdown_pct": {"type": "number"},
                    "num_holdings": {"type": "integer"},
                },
                "required": ["equity_pct", "bond_pct", "cash_pct", "risk_level", "fee_ratio", "max_drawdown_pct", "num_holdings"],
            },
        },
        {
            "name": "detect_regime",
            "description": "检测市场周期（牛/熊/震荡）及宏观乘数",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "current": {"type": "number"},
                    "ma200": {"type": "number"},
                    "ma120": {"type": "number"},
                    "risk_level": {"type": "string"},
                },
                "required": [],
            },
        },
        {
            "name": "manage_personal_rules",
            "description": "管理个人投资红线规则（增/删/查/清）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "add/remove/list/clear"},
                    "rule_id": {"type": "string"},
                    "description": {"type": "string"},
                    "fund_types_blacklist": {"type": "string"},
                    "max_single_position": {"type": "number"},
                    "min_fund_size": {"type": "number"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "screen_funds",
            "description": "筛选并评分基金列表 — 统一5维度加权评分",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "funds": {"type": "array"},
                    "min_net_asset_value": {"type": "number"},
                    "allowed_types": {"type": "string"},
                    "max_fee_rate": {"type": "number"},
                    "risk_level": {"type": "string", "description": "conservative|moderate|aggressive"},
                },
                "required": ["funds"],
            },
        },
    ],
}

# ── Tool dispatch ────────────────────────────────────────────────────

_TOOLS = {
    "assess_risk": ("src.tools.risk", "assess_risk"),
    "get_allocation": ("src.tools.portfolio", "get_allocation"),
    "get_advice": ("src.tools.advisory", "get_advice"),
    "audit_single_fund": ("src.tools.audit", "audit_single_fund"),
    "run_scenario": ("src.tools.scenario", "run_scenario"),
    "lookup_fund": ("src.tools.market", "lookup_fund"),
    "lookup_index": ("src.tools.market", "lookup_index"),
    "list_hard_rules": ("src.tools.rules", "list_hard_rules"),
    "check_health": ("src.tools.health", "check_health"),
    "detect_regime": ("src.tools.macro", "detect_regime"),
    "manage_personal_rules": ("src.tools.personal_rules", "manage_personal_rules"),
    "screen_funds": ("src.tools.screener", "screen_funds"),
}


def handle_task(task_name: str, arguments: dict) -> dict:
    """Dispatch an A2A task to the correct fortress tool.

    Returns the tool result as a dict suitable for A2A Task artifact.
    """
    if task_name not in _TOOLS:
        return {"error": f"Unknown task: {task_name}", "available": list(_TOOLS.keys())}

    module_name, func_name = _TOOLS[task_name]
    try:
        # Ensure fortress src/ is on path
        fortress_root = Path(__file__).resolve().parent.parent.parent
        if str(fortress_root) not in sys.path:
            sys.path.insert(0, str(fortress_root))

        module = __import__(module_name, fromlist=[func_name])
        func = getattr(module, func_name)
        return func(**arguments)
    except Exception as e:
        return {"error": str(e), "task": task_name}


# ── Standalone server (experimental) ─────────────────────────────────

def main():
    """Start a minimal A2A-compatible HTTP server.

    WARNING: Experimental. Uses a2a-sdk v1.1.0 whose public API is still evolving.
    For production, use the MCP path (python -m src.tools.server).
    """
    try:
        from a2a.server.apps import A2AStarletteApplication
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.agent_execution import AgentExecutor
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.types import TaskState, TextPart
        import uvicorn
    except ImportError as e:
        logger.info("A2A SDK not fully available: %s", e)
        logger.info("Install: pip install a2a-sdk[http-server] uvicorn")
        logger.info("For production use, connect via MCP: python -m src.tools.server")
        sys.exit(1)

    class FortressExecutor(AgentExecutor):
        async def execute(self, context, event_queue):
            task_name = context.task_id.split(":")[0] if ":" in context.task_id else context.task_id
            # Extract arguments from the message
            message_text = ""
            if context.message and context.message.parts:
                for part in context.message.parts:
                    if hasattr(part, 'text'):
                        message_text += part.text
            try:
                arguments = json.loads(message_text) if message_text.strip() else {}
            except json.JSONDecodeError:
                arguments = {"message": message_text}

            result = handle_task(task_name, arguments)

            from a2a.server.task_updater import TaskUpdater
            updater = TaskUpdater(event_queue, context.task_id, context.context_id)
            await updater.start_work()
            await updater.complete(
                message=updater.new_agent_message(
                    parts=[TextPart(text=json.dumps(result, ensure_ascii=False, default=str))]
                )
            )

    card = AGENT_CARD
    handler = DefaultRequestHandler(
        agent_executor=FortressExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(agent_card=card, http_handler=handler)
    port = int(os.environ.get("FORTRESS_A2A_PORT", "8080"))
    logger.info("Fortress A2A server starting on port %d", port)
    logger.info("Agent Card: http://localhost:%d/.well-known/agent.json", port)
    uvicorn.run(app.build(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
