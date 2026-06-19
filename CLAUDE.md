# CLAUDE.md — Fortress (AI 投资顾问 v2.0)

## 项目概述
对话式 AI 投资顾问 Agent Skill。三条路径：底仓配置（求确定性）+ 机会捕捉（求收益）+ 持仓诊断（求安心）。

## 核心架构
- **数据模型**: GnuCash 三实体 — Split / Transaction / Account，延迟约束校验
- **Agent 管线**: LangGraph DAG 四阶段 — 数据采集→多空辩论→建议→风险评估
- **组合优化**: Riskfolio-Lib — Entropy Pooling 适配 LLM 主观观点
- **红线规则**: 分层 — hard_rules（通用不可关）+ personal_rules（用户可配置）

## 项目策略
- 当前处于 **Phase 2** — 数据层实现（三实体账本 + SQLite + 数据源适配器）
- 规格文档: `docs/specs/`
- 从 v0.x (finance_skill) 移植策略逻辑，架构全部重写
- 双平台：Claude Code MCP + Hermes Agent

## 关键约束
- engine/ 层零 I/O 纯函数
- 所有金额 `decimal.Decimal`
- 永不自动交易，永不推荐个股
- 数据隔离（每用户独立 SQLite）
