# LLM Debater Integration Plan

> 2026-06-20 | fortress v2.0

## Dependency Graph

```
prompt template (pure text)
       │
       ▼
LLM client (call_llm function)
       │
       ▼
debater node update (wired into LangGraph)
       │
       ▼
E2E: live Claude call (integration, xfail without key)
```

## Tasks

### T1: Prompt Template — `src/agent/prompts.py`
- [ ] `build_debate_prompt(market_data, holdings) -> str`
- [ ] 约束注入：不推荐个股、不触发交易、免责声明
- [ ] Bull x3 + Bear x3 + 综合判断 结构化输出格式
- [ ] Test: `tests/agent/test_prompts.py` — 验证约束词出现在 prompt 中

### T2: LLM Client — `src/agent/llm.py`
- [ ] `call_llm(prompt: str) -> str` — 调用 Claude API
- [ ] 从环境变量读 `ANTHROPIC_API_KEY`
- [ ] 错误处理：API 不可用时返回含错误信息的降级输出
- [ ] Test: `tests/agent/test_llm.py` — mock httpx，验证调用参数

### T3: Debater Node Update — `src/agent/nodes/debater.py`
- [ ] 替换硬编码文本为 `call_llm(build_debate_prompt(...))`
- [ ] 无 market_data 时仍返回错误（保持现有行为）
- [ ] Test: `tests/agent/test_nodes.py` — mock call_llm，验证状态更新

### T4: E2E Live Call — `tests/integration/test_llm_integration.py`
- [ ] 真实 Claude API 调用（标记 integration + xfail without key）
- [ ] 验证输出包含 多方/空方/综合判断 三段

## Checkpoint

```
T1 ✅ → T2 ✅ → T3 ✅ → T4 ✅ → 170+ unit + 2 integration green
```

## New Dependencies

```
anthropic>=0.40  # Anthropic Python SDK (may already be installed)
```
