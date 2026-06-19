"""A2A (Agent-to-Agent) adapter for Hermes Agent compatibility.

## Status: STUB — implementation pending A2A SDK availability

The fortress core engine (engine/ + data/ + agent/) is protocol-agnostic.
This module provides the A2A adapter layer that wraps the same 6 tool
functions for Hermes Agent.

## What's needed to complete

1. Install A2A Python SDK (not yet available on PyPI at time of writing)
2. Create an Agent Card JSON advertising fortress capabilities
3. Register 6 tasks (one per tool) with input/output schemas
4. Start A2A server (similar to MCP's `server.run()`)

## Architecture

```
Hermes Agent
    │  A2A protocol (HTTP/JSON-RPC)
    ▼
a2a_adapter.py   # Task handlers wrapping the same tool functions
    │
    ▼
src/tools/*.py   # Shared tool implementations (protocol-agnostic)
    │
    ▼
src/engine/ + src/data/ + src/agent/   # Core engine (unchanged)
```

## Estimated effort

~200 lines of code, reusing existing tool implementations.
No engine/data/agent changes needed.
"""

# ── Placeholder — implement when A2A SDK is available ────────────────

TOOLS = {
    "assess_risk": {
        "description": "5-factor risk profile assessment",
        "inputs": ["horizon", "max_loss_pct", "income", "experience", "liquidity"],
    },
    "get_allocation": {
        "description": "Build 3-layer allocation plan",
        "inputs": ["risk_level", "total_amount"],
    },
    "get_advice": {
        "description": "Full advisory report (paths A/B/C)",
        "inputs": ["path", "message", "equity", "bond", "cash"],
    },
    "audit_single_fund": {
        "description": "Audit fund against redline rules",
        "inputs": ["code", "name", "fund_type", "net_asset_value", "fee_rate", "inception_date", "planned_amount"],
    },
    "run_scenario": {
        "description": "Stress test portfolio against scenarios",
        "inputs": ["equity", "bond", "cash", "scenario_name"],
    },
    "lookup_fund": {
        "description": "Look up fund info and NAV",
        "inputs": ["code"],
    },
}

# Agent Card (A2A discovery document)
AGENT_CARD = {
    "name": "fortress",
    "description": "AI 投资顾问 — 对话式基金/ETF 组合管理",
    "version": "0.1.0",
    "url": "http://localhost:8080",  # configure per deployment
    "capabilities": {"tasks": True},
    "tasks": [
        {
            "name": name,
            "description": meta["description"],
            "inputSchema": {"type": "object", "properties": {p: {"type": "string"} for p in meta["inputs"]}},
        }
        for name, meta in TOOLS.items()
    ],
}
