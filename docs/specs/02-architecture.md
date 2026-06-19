# Architecture Decision Record — Fortress v2.0

> 基于 Phase 0.5 调研（MCP/A2A 对比、LangGraph 替代评估、akshare 稳定性审计、GitHub 高星项目对标）的最终架构决策。

## ADR-1: 通信协议 — MCP

**决策**: 使用 Model Context Protocol (MCP)，不引入 A2A。

**理由**:
- 堡垒是单 Agent Skill，不是多 Agent 系统。MCP 的 Agent↔工具模型完全覆盖需求。
- MCP 生态成熟：Anthropic/OpenAI/Google 均支持，10000+ 可用 server。
- A2A 解决跨 Agent 协调问题（Agent Card 发现、任务委派、多跳路由），堡垒当前不需要。
- 如果未来引入多 Agent（如独立的市场监控 Agent + 投顾 Agent），可在 MCP 之上叠加 A2A——二者互补而非竞争。

**备选**: A2A（延后到多 Agent 需求出现时评估）

**参考**: [Cisco MCP/A2A 心智模型](https://blogs.cisco.com/ai/mcp-and-a2a-a-network-engineers-mental-model-for-agentic-ai), [Atlan MCP vs A2A](https://atlan.com/know/mcp/mcp-vs-a2a-protocol/)

---

## ADR-2: Agent 框架 — LangGraph

**决策**: 使用 LangGraph 构建 Agent DAG，不自研轻量 pipeline。

**理由**:
- **行业验证**: GitHub 调研 6/7 高星金融 Agent 项目用 LangGraph。TradingAgents (85.8k⭐) 是最直接对标。
- **迁移成本**: FenixAI v2.0 从 CrewAI 迁到 LangGraph 的教训——自研轻量 DAG 在遇到循环、人机交互、状态持久化需求时迁移成本高。
- **内置能力**: Checkpointer（状态持久化）、interrupt（人机交互）、conditional edges（条件路由）——路径 B（机会捕捉）的"市场异动→影响分析→多空辩论→调仓建议"正好需要条件路由。
- **LangChain 解耦**: LangGraph 可独立于 LangChain 使用。我们只依赖 `langgraph` 包，不引入 `langchain`。

**备选**: 自研 DAG（延后——如 LangGraph 在实践中有不可接受的复杂度，再评估 `shortgraph` 或自研）

**参考**: [TradingAgents](https://github.com/TauricResearch/TradingAgents), [FenixAI v2.0](https://github.com/Ganador1/FenixAI_tradingBot), [Langfuse 框架对比](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)

---

## ADR-3: 数据模型 — GnuCash 三实体 + 延迟约束

**决策**: 采用 Split / Transaction / Account 三实体模型，延迟约束校验。

**理由**:
- GnuCash 24 年工业验证——该模型已处理过几乎所有边缘情况。
- 延迟约束（后置 Scrub）适合现实世界的脏数据：用户可能先录入交易再补全信息，先估算金额再精确修正。
- 与复式记账兼容——每笔 Transaction 至少两个 Split（借贷平衡），天然适合审计追踪。

**实现要点**:
```python
# Account: 账户（基金/现金/应收/应付）
# Transaction: 一笔交易（申购/赎回/分红/转换）
# Split: 交易的一条腿（借记/贷记，指向一个 Account）
# 约束: SUM(Split.amount) == 0 per Transaction（延迟校验）
```

---

## ADR-4: 组合优化 — Riskfolio-Lib

**决策**: Riskfolio-Lib 替代 PyPortfolioOpt。

**理由**:
- 26 种风险度量 vs PyPortfolioOpt 的 5 种。
- Entropy Pooling 方法天然适配 LLM 主观观点输入（Black-Litterman 的现代化替代）。
- 6 类锥规划求解器，覆盖均值-方差、CVaR、CDaR、最大回撤等。

---

## ADR-5: 数据源 — akshare 为主 + 三级降级

**决策**: akshare（主）→ 天天基金直连（备）→ 本地 SQLite 缓存（兜底）

**理由**:
- akshare 是唯一覆盖中国基金/ETF 全量数据的免费 Python 库。
- **但**: 2025-2026 年稳定性显著恶化（东财反爬升级、频率限制、Schema 易变）。不适合实时/高频场景。
- 堡垒使用日频/周频数据（不要求实时行情），akshare + 重试 + 缓存可以满足需求。
- 三级降级设计参考 WhenTrade 多源故障转移模式。

**降级触发条件**:
| 条件 | 动作 |
|------|------|
| akshare 超时 >5s | 重试 3 次（指数退避 1s/2s/4s） |
| 重试耗尽 | 切换到天天基金直连 |
| 天天基金也失败 | 使用本地缓存（如有 24h 内数据） |
| 缓存也不可用 | 报告数据不可用，不阻塞流程 |

**akshare 调用铁律**:
- 间隔 ≥2s（东财）/ ≥5s（新浪）
- 并发 ≤5
- 指定时间范围（禁止默认拉全量历史）
- 禁止 `ThreadPoolExecutor` 高并发

---

## ADR-6: 数据库 — 多 SQLite 文件隔离

**决策**: 每个用户独立 SQLite 文件。

**理由**:
- 零配置——无需 PostgreSQL 安装。
- 天然隔离——物理文件级隔离，操作失误不影响其他用户。
- 备份简单——复制文件即可。
- 单用户数据量预估 <100MB（持仓+交易+基金元数据），SQLite 轻松应对。

**路径约定**: `{DATA_DIR}/{user_id}/portfolio.db`

---

## ADR-7: 前端交互 — 纯对话 + HTML 报告片段

**决策**: 对话式交互，报告以 HTML 片段在对话内渲染。

**理由**:
- 堡垒是 Agent Skill，不是独立 Web 应用。用户通过 Claude Code / Hermes Agent 对话界面交互。
- HTML 片段支持表格、图表（ECharts/Plotly 嵌入式）、颜色标记（涨跌红绿），对话内渲染足够表达六段式报告。
- 参考 trading-agents-plugin 做 Claude Code slash command 分发。
- 可选 Web UI 延后到 v3.0（如有需求）。

---

## ADR-8: 红线规则 — 声明式 DSL + 分层

**决策**: 声明式规则 DSL，hard_rules（不可关）+ personal_rules（用户可配）

**理由**:
- 声明式 = 读规则即读意图。非技术人员可大致理解规则。
- 分层 = 风控底线（hard）与偏好（personal）分离。hard_rules 审计合规不可绕过；personal_rules 用户可在对话中调整。

**DSL 设计**:
```python
RULE_FUND_MIN_SIZE = RedLine(
    id="RL-001",
    severity="reject",  # reject | warn
    condition=lambda f: f.net_asset_value < Decimal("200_000_000"),
    message="基金规模 < 2亿，单客户持仓 ≤ 5万"
)
```

---

## ADR-9: LLM 架构 — Skill 作为领域计算引擎

**决策**: 堡垒是领域知识引擎（计算 + 规则），不是自主 LLM Agent。
宿主 LLM（Claude Code / Hermes）负责自然语言叙事，堡垒负责结构化信号计算。

**理由**:
- 堡垒作为 Skill 嵌入 Claude Code，宿主 LLM 自带语言能力。Skill 不应有自己的 API key。
- 引擎层（PE 分位、波动率、规模阈值）是宿主 LLM 无法执行的计算——这是 Skill 的独特价值。
- 分离关注点：Skill = 量化信号；宿主 LLM = 语言包装。各司其职。

**架构**:
```
用户对话 → 宿主 LLM 理解意图 → 调用 MCP tools → 堡垒引擎计算 → 结构化信号返回 → 宿主 LLM 叙事
```

**debater 节点**: 输出结构化 DebateSignals（bull_signals + bear_signals + conclusion_framework），
而非 LLM 生成的文本。信号来源于纯计算——PE 分位、波动率评估、分散度检查。

**独立模式**: `src/agent/llm.py` 保留为可选适配器。
设置 `FORTRESS_LLM=deepseek` + `DEEPSEEK_API_KEY` 可脱离宿主独立运行。
默认模式无需任何外部 API key。

---

## 组件架构图

```
┌─────────────────────────────────────────────────────┐
│                   宿主 LLM                           │
│         Claude Code / Hermes Agent                  │
│         （自然语言理解 + 叙事生成）                    │
└──────────────────────┬──────────────────────────────┘
                       │ MCP 协议
┌──────────────────────▼──────────────────────────────┐
│                 src/tools/                           │
│  MCP 工具注册层 — 6 工具 + FastMCP server            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 src/agent/                           │
│  LangGraph DAG — 四阶段管线                          │
│  data_collector → debater → allocator → risk_assessor│
│  状态 Schema: ConversationState                      │
└────────┬─────────────────────────────┬──────────────┘
         │                             │
┌────────▼──────────┐     ┌────────────▼──────────────┐
│   src/engine/     │     │      src/data/            │
│   纯函数引擎       │     │      I/O 管线             │
│  • ledger         │     │  • market (数据源适配器)    │
│  • risk_profile   │     │  • portfolio_db (CRUD)    │
│  • allocation     │     │  • cache (本地缓存)        │
│  • screener       │     │  • sources/               │
│  • auditor        │     │    - eastmoney             │
│  • optimizer      │     │    - tiantian              │
│  • stress_tester  │     │    - akshare               │
│  • health_checker │     │                           │
└────────┬──────────┘     └────────────┬──────────────┘
         │                             │
┌────────▼─────────────────────────────▼──────────────┐
│              src/redlines/                           │
│  hard_rules.py (不可关) + personal_rules.py (可配)    │
└─────────────────────────────────────────────────────┘
```

---

## 数据流 — 三条路径

### 路径 A: 底仓配置
```
用户 → 风险测评(risk_profile) → 三层架构比例(allocation)
     → 产品筛选(screener) → 单品审计(auditor + redlines)
     → 组合优化(optimizer → BL + Entropy Pooling)
     → 压力测试(stress_tester) → 配置方案报告
```

### 路径 B: 机会捕捉
```
市场异动(market) → 影响分析 → Bull/Bear 辩论(debater)
                → 调仓建议(allocator) → 风险评估(risk_assessor)
                → 确认执行
```

### 路径 C: 持仓诊断
```
用户触发/定期巡检 → 拉取持仓(portfolio_db)
                  → 层级偏离检查(allocation)
                  → 单品审计(auditor + redlines)
                  → 压力测试重跑(stress_tester)
                  → 健康评分(health_checker)
                  → 六段式诊断报告
```

---

## 关键约束（不变）

- `engine/` 零 I/O — 纯函数，接收数据返回结果
- 所有金额 `decimal.Decimal`
- 永不自动交易，永不推荐个股
- 数据隔离（每用户独立 SQLite）
- 网络调用前 `unset http_proxy https_proxy`

---

*ADR v1.0 — Phase 1 完成。进入 Phase 2: 数据层实现。*
