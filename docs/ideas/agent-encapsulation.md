# 堡垒 Agent 封装 — 三条路径显式化

## Problem Statement
How might we 让 Fortress 用户不需要理解 `path=A/B/C` 和 5 个 DAG 节点的内部编排，而用 "帮我做底仓配置" 这样的自然意图直接触发正确的计算管线？

## Recommended Direction
**变体 1: 纯薄包装。** 在现有 `get_advice(path, ...)` 之上加 3 个命名 MCP tool——`底仓配置`、`机会捕捉`、`持仓诊断`——每个工具固定对应一条 DAG 路径。底层 DAG 完全不变，`get_advice` 向后兼容保留。

选择理由：
- 改动量 < 100 行，风险极低
- 最接近 CFSC 的 Agent 模式（独立命名入口）
- 为后续 Plugin Marketplace（变体 5）预留扩展点

## Target Users & Success Criteria
- **个人投资者**：能通过 "使用底仓配置工具" 直接触发，不再需要理解 path=A/B/C
- **投顾顾问**：能对客户说 "我用堡垒的持仓诊断帮你看看"，工具名自解释
- **成功指标**：`claude mcp list-tools fortress` 输出中出现 3 个中文名 tool，每个 tool 的 description 清晰描述用途

## Key Assumptions to Validate
- [ ] **用户确实因为语义不透明而不使用 Fortress** — 部署后观察 3 个新 tool 的调用频率是否显著高于原 `get_advice`
- [ ] **3 个 Agent 的输入参数无需分化** — 已验证：所有路径共享 `ConversationState`，参数完全一致
- [ ] **中文 tool 名在 MCP 协议中无兼容问题** — FastMCP 使用 Python 函数名作为 tool name，需确认是否支持中文

## MVP Scope

**In scope:**
- `advisory_agents.py` — Agent 元数据注册表（名称、路径映射、描述）
- `advisory.py` 中 3 个薄函数：`底仓配置`、`机会捕捉`、`持仓诊断`
- `server.py` 中 3 个 `@server.tool()` 注册
- `tests/tools/test_advisory_agents.py` — 验证 3 个 Agent 正确路由到对应路径

**Out of scope:**
- 每个 Agent 的独立系统 prompt
- Agent 间互调编排
- Plugin Marketplace 注册

## Not Doing (and Why)
- **Agent 独立子图** — 3 条路径的节点组合尚未分化，不需要拆分 DAG。过早拆分会导致状态管理复杂度
- **Agent prompt 文件（CFSC 模式）** — Fortress 还没有 skill-as-document 的机制，引入这个抽象层会过度设计。等 managed-agent 部署时再考虑
- **合并为智能路由** — LLM 可能误判用户意图（持仓诊断 vs 机会捕捉），牺牲了 Fortress 计算引擎的确定性优势

## Implementation Plan
1. 创建 `advisory_agents.py`（Agent 元数据注册表）
2. 在 `advisory.py` 添加 3 个薄包装函数
3. 在 `server.py` 注册 3 个新 MCP tool
4. 运行 `pytest tests/ -k "advisory"` 确保向后兼容
5. 运行 `python scripts/healthcheck.py` 确保端到端通过

## Open Questions
- FastMCP 是否支持中文函数名作为 tool name？如果不支持，用拼音或英文映射
- 是否需要给每个 Agent tool 添加 usage examples 在 docstring 中？
