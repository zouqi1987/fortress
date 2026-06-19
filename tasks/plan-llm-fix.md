# LLM Architecture Fix Plan

> 2026-06-20 | fortress v2.0

## Principle

堡垒是 **领域知识引擎**（计算 + 规则），不是自主 LLM Agent。
宿主 LLM（Claude Code）负责自然语言包装，堡垒负责结构化信号。

## Tasks

### T1: Remove external LLM dependency
- [ ] `pyproject.toml`: remove `anthropic` from dev-deps
- [ ] `pip uninstall anthropic` from venv (optional, harmless if stays)
- [ ] Verify all existing tests still pass without anthropic installed

### T2: prompts.py → signals.py (结构化信号定义)
- [ ] Rename: `src/agent/prompts.py` → `src/agent/signals.py`
- [ ] Define `Signal` dataclass: `{name, value, interpretation, direction}`
- [ ] Define `DebateSignals`: `{bull_signals, bear_signals, conclusion_framework}`
- [ ] `extract_signals(market_data, holdings) -> DebateSignals` (纯函数，零 LLM)
- [ ] Tests: `tests/agent/test_signals.py`

### T3: llm.py → optional standalone adapter
- [ ] 保留为可选适配器，默认不调用
- [ ] 支持 `FORTRESS_LLM=deepseek` 环境变量
- [ ] 无外部依赖时的降级不变
- [ ] Tests unchanged: `tests/agent/test_llm.py` keeps passing

### T4: debater node → signal-driven
- [ ] 替换 `call_llm(build_debate_prompt(...))` 为 `extract_signals(...)`
- [ ] 输出结构化信号 dict（宿主 LLM 根据信号自然生成辩论文本）
- [ ] Tests: `tests/agent/test_nodes.py` 验证信号结构

### T5: Verify E2E
- [ ] 181 unit tests pass without anthropic
- [ ] E2E healthcheck passes
- [ ] MCP tool `get_advice` still produces valid reports

## New Architecture

```
宿主 LLM (Claude Code / Hermes)
    │
    │ 调用 MCP tools: get_advice(path="B", ...)
    ▼
skill: debater node
    │
    ├─ signals.py: extract_signals(market_data, holdings)
    │     └─ 纯计算: PE分位, 波动率, 资金流向阈值
    │     └─ 输出: {"bull_signals": [...], "bear_signals": [...], ...}
    │
    └─ 宿主 LLM 接收信号 → 自然语言辩论
          "基于信号分析，多方认为估值处于28%分位..."
```

## Out of Scope
- DeepSeek API 实现（llm.py 保留接口，不实现具体调用）
- 实时行情信号（需要更多数据源）

## Files Changed
```
M pyproject.toml          — remove anthropic
M src/agent/prompts.py    → src/agent/signals.py  (rename + rewrite)
M src/agent/llm.py        — add optional DeepSeek support note
M src/agent/nodes/debater.py  — use extract_signals()
M tests/agent/test_prompts.py → tests/agent/test_signals.py
M tests/agent/test_nodes.py   — update debater assertions
```
