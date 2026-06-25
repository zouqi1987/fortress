# CLAUDE.md — Fortress AI 投资顾问

## 项目概述
对话式 AI 投资顾问 Agent Skill。三条路径：底仓配置（求确定性）+ 机会捕捉（求收益）+ 持仓诊断（求安心）。

## 核心架构
- **数据模型**: GnuCash 三实体 — Split / Transaction / Account，延迟约束校验
- **Agent 管线**: LangGraph DAG 五节点 — 数据采集→多空辩论→配置→风险评估→报告
- **组合优化**: Scipy SLSQP — 最小方差优化，支持权重上下界约束
- **评分体系**: 统一 5 维度加权 — 机构共识/同类业绩/风控/持续性/费率，9 组权重（3 基金类型 × 3 风险画像），基于 Morningstar Medalist + 济安金信方法论
- **NAV 存储**: NavStore (SQLite) — 全市场 23,784 只基金，28.3M 数据点，24.8 年历史，启动时自动检查完备性
- **红线规则**: 分层 — hard_rules（通用不可关）+ personal_rules（用户可配置）
- **MCP 工具**: 16 个自描述工具，覆盖风险测评→配置→筛选→审计→压测→健康全流程

## 项目状态
- 全模块实现完成，426 测试通过
- 规格文档: `docs/specs/` (含统一评分系统 spec 06-08)
- 双平台：Claude Code MCP (生产) + Hermes Agent (A2A 实验性)
- 数据源: akshare → eastmoney/tiantian → SQLite 缓存三级降级
- NAV 数据: GitHub Release 备份 (545 MB 压缩，含 23K 基金完整历史)

# 核心行为准则
1. 在回答任何关于代码修改、Bug 修复或架构设计的请求之前，**必须**先调用相关的搜索/读取技能（如阅读代码、检索结构），严禁凭空盲写。
2. 任何时候需要确认运行结果，**必须**调用终端执行技能运行测试或服务，以实际的报错或日志为准。
3. 严禁基于猜测进行开发。如果你不确定某个函数的定义，立即调用技能去查，而不是直接生成。

## 关键约束
- engine/ 层零 I/O 纯函数
- 所有金额 `decimal.Decimal`
- 永不自动交易，永不推荐个股
- 数据隔离（每用户独立 SQLite）
- 所有数据来自实时 API，不硬编码
- 金融项目原则：数据缺失时排除基金，绝不捏造分数（InsufficientDataError）
- 每阶段实现后必须做正式 5-axis review（correctness/readability/architecture/security/performance）
