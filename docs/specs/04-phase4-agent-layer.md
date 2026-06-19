# Phase 4 Agent Layer Design

> 2026-06-19 | fortress v2.0

## Scope

LangGraph DAG with 5 nodes + routing graph for three user paths (A/B/C).

**Out of scope**: MCP tool registration (Phase 6), redline DSL extraction (Phase 5).

---

## 1. State — `src/agent/state.py`

```python
class ConversationState(TypedDict):
    # User input
    path: str                    # "A" | "B" | "C"
    user_message: str
    # Collected data (populated by nodes)
    risk_profile: RiskProfile | None
    portfolio: dict | None       # {"equity": D, "bond": D, "cash": D}
    market_data: dict | None     # code → NAVPoint[]
    holdings: list | None        # current positions
    # Analysis
    debate_result: str | None    # Bull/Bear summary
    allocation_plan: AllocationPlan | None
    audit_results: list[AuditResult] | None
    stress_result: StressResult | None
    health_check: HealthCheckResult | None
    # Output
    report_html: str | None
    errors: list[str]
```

## 2. Nodes — `src/agent/nodes/`

| Node | Function | Input | Output |
|------|----------|-------|--------|
| `data_collector` | Fetch portfolio + market data via data/ layer | state | state with populated data |
| `debater` | Bull vs Bear analysis (path B only) | state | state with debate_result |
| `allocator` | Run allocation + screening + optimization | state | state with allocation_plan |
| `risk_assessor` | Run risk profile + stress test + health check | state | state with risk + stress + health |
| `reporter` | Format final HTML/Markdown report | state | state with report_html |

## 3. Graph — `src/agent/graph.py`

```
Path A (底仓配置):
  data_collector → allocator → risk_assessor → reporter

Path B (机会捕捉):
  data_collector → debater → allocator → risk_assessor → reporter

Path C (持仓诊断):
  data_collector → risk_assessor → reporter
```

## 4. Files

```
src/agent/
├── __init__.py
├── state.py           # ConversationState TypedDict
├── graph.py           # build_graph() → compiled LangGraph
└── nodes/
    ├── __init__.py
    ├── data_collector.py
    ├── debater.py
    ├── allocator.py
    ├── risk_assessor.py
    └── reporter.py
tests/agent/
├── __init__.py
├── test_state.py
├── test_nodes.py
└── test_graph.py
```

## 5. Testing Strategy

- **State**: validate TypedDict keys, default values
- **Nodes**: mock data/ and engine/ dependencies, verify state transitions
- **Graph**: verify routing (A→data→alloc→risk→report, B→data→debate→alloc→risk→report, C→data→risk→report)
- **Integration**: full graph invoke with mock data sources
