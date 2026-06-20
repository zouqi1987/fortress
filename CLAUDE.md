# CLAUDE.md — Fortress AI 投资顾问

## 项目概述
对话式 AI 投资顾问 Agent Skill。三条路径：底仓配置（求确定性）+ 机会捕捉（求收益）+ 持仓诊断（求安心）。

## 核心架构
- **数据模型**: GnuCash 三实体 — Split / Transaction / Account，延迟约束校验
- **Agent 管线**: LangGraph DAG 五节点 — 数据采集→多空辩论→配置→风险评估→报告
- **组合优化**: Riskfolio-Lib — Entropy Pooling 适配 LLM 主观观点
- **红线规则**: 分层 — hard_rules（通用不可关）+ personal_rules（用户可配置）

## 项目状态
- 全模块实现完成，240 测试通过
- 规格文档: `docs/specs/`
- 双平台：Claude Code MCP + Hermes Agent
- 数据源: akshare → eastmoney 直连 → SQLite 缓存三级降级

## 关键约束
- engine/ 层零 I/O 纯函数
- 所有金额 `decimal.Decimal`
- 永不自动交易，永不推荐个股
- 数据隔离（每用户独立 SQLite）
- 所有数据来自实时 API，不硬编码
