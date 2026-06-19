# Phases 4-7 Implementation Plan

> 2026-06-19 | fortress v2.0

## Phase 4: Agent Layer (LangGraph DAG)
| # | Task | Files |
|---|------|-------|
| 4.1 | ConversationState schema | `src/agent/state.py` |
| 4.2 | 5 nodes (data_collector, debater, allocator, risk_assessor, reporter) | `src/agent/nodes/*.py` |
| 4.3 | Graph routing (paths A/B/C) | `src/agent/graph.py` |
| 4.4 | Agent tests | `tests/agent/` |

## Phase 5: Redline Rules DSL
| # | Task | Files |
|---|------|-------|
| 5.1 | Rule DSL + hard_rules + personal_rules | `src/redlines/` |
| 5.2 | Rule engine tests | `tests/redlines/` |

## Phase 6: MCP Tool Registration
| # | Task | Files |
|---|------|-------|
| 6.1 | 6 MCP tools (risk, portfolio, advisory, audit, scenario, market) | `src/tools/` |
| 6.2 | SKILL.md (platform-agnostic skill definition) | `SKILL.md` |
| 6.3 | `.mcp.json` (MCP configuration) | `.mcp.json` |

## Phase 7: E2E + Docs
| # | Task | Files |
|---|------|-------|
| 7.1 | E2E smoke test script | `scripts/healthcheck.py` |
| 7.2 | README.md | `README.md` |

**Total: 9 tasks, ~12 files**
