# SPEC: AI 投资顾问 v2.0（项目代号：fortress）

> 基于深度调研 24 份源、94 条主张、25 条 3-0 对抗验证的架构决策

## 调研摘要

**确认采纳（高置信度）：**

| 来源 | 可借鉴范式 | 应用到本系统 |
|------|----------|------------|
| GnuCash (24年工业级) | 三实体模型 (Split/Transaction/Account) + 延迟约束校验 | 持仓/交易数据层——允许灵活录入，后置 Scrub 修复不平衡 |
| TradingAgents (AAAI 2025) | 12 专家 Agent + LangGraph DAG + Bull-vs-Bear 辩论 | 投顾推理管线——数据采集→多空辩论→建议→风险评估 |
| Riskfolio-Lib v7.3 | 26 种风险度量 + 6 类锥规划 + Entropy Pooling | 组合优化层——替代 PyPortfolioOpt，Entropy Pooling 更适合 LLM 输入 |
| Beancount | 本土化 lot 追踪 + 自动资本利得计算 + Python 可扩展 | 投资记账参考——成本基础追踪、税务计算 |

**确认排除（0-3 或 1-2 投票）：** FinGPT 架构、FinCon 多代理系统、skfolio API 模式、CPPO-DeepSeek RL 方法

**调研留白（无主张通过验证）：** 量化框架（vnpy/backtrader/zipline/qlib）、数据源对比、AI Agent 框架独立评估——这些方向需自行判断

---

## 1. Objective

构建一个**对话式 AI 投资顾问系统**，以 Agent Skill 形态分发，任何人安装后通过对话完成：**底仓配置（求稳）→ 机会捕捉（求增）→ 持仓诊断（求安）**。对标蚂蚁财富的引导式体验，但通过对话界面实现。

### 目标用户
- **主要：** 中国个人投资者，有基金/ETF 持仓，需要系统性配置建议
- **次要：** 投资新手，通过风险测评→资产配置引导完成首次配置

### 用户故事（核心三条路径）

**路径 A — 底仓配置（求确定性）**
```
新用户 → 风险测评（5因子） → 个性化三层架构比例 → 产品筛选+审计
→ 首次配置方案 → 模拟压力测试 → 确认执行
```

**路径 B — 机会捕捉（求收益）**
```
市场异动触发 → 主动推送通知 → 影响分析（我的持仓哪些受影响）
→ 机会评估（多空辩论） → 调仓建议（如有） → 确认执行
```

**路径 C — 持仓诊断（求安心）**
```
定期巡检/用户触发 → 拉取持仓数据 → 层级偏离检查 → 单品审计
→ 压力测试重跑 → 健康评分 → 诊断报告 + 行动建议
```

### 成功标准
- 新用户 10 分钟内完成风险测评→首次配置建议
- 持仓诊断输出一致的六段式报告（持仓→层级→单品→调整→压测→时序）
- 市场异动到主动通知延迟 < 5 分钟（数据源允许）
- 90%+ 的基金代码可通过单品审计（天天基金可查）
- 双平台兼容（Claude Code MCP + Hermes Agent）

---

## 2. 推荐技术栈（调研驱动，待最终确认）

| 层级 | 推荐方案 | 替代方案 | 调研依据 |
|------|---------|---------|---------|
| **语言** | Python 3.12+ | TypeScript (Bun) | Riskfolio-Lib/akshare/Beancount 均为 Python 生态 |
| **Agent 框架** | LangGraph | Rillab's Agent Framework, 自研 | TradingAgents 用 LangGraph 通过 3-0 验证 |
| **数据模型** | 三实体 (Split/Transaction/Account) | 传统复式记账 | GnuCash 24 年工业验证，延迟约束适合乱数据 |
| **组合优化** | Riskfolio-Lib | PyPortfolioOpt | 26 风险度量 vs 5 种；Entropy Pooling 适配 LLM 输入 |
| **市场数据** | akshare + 天天基金直连 | tushare, yfinance | v0.x 验证可用；Yahoo Finance 中国 IP 超时 |
| **数据库** | SQLite（本地优先）| PostgreSQL | 零配置启动需求；多用户通过独立 DB 文件隔离 |
| **通信协议** | 调研后决定 | - | MCP（已验证）或 A2A（Google Agent-to-Agent）待评估 |
| **后端模式** | 纯工具调用（无独立 server）| FastAPI server | 作为 Skill 无需独立部署；DB 本地 SQLite |
| **测试** | pytest + pytest-cov | - | Python 生态标准 |

### 待调研项（Phase 0.5）
- MCP vs A2A 协议对比（多平台兼容性、流式支持、状态管理）
- LangGraph vs 轻量级替代（自研 DAG、Prefect）
- akshare 稳定性数据（频率限制、数据延迟、错误率）

---

## 3. 项目结构

```
fortress/
├── README.md
├── SKILL.md
├── CLAUDE.md
├── .mcp.json
├── pyproject.toml
├── .github/workflows/test.yml    # CI
├── docs/specs/
│   ├── 01-system-spec.md
│   ├── 02-architecture.md        # 9 ADRs
│   ├── 03-phase2-data-layer.md
│   └── 04-phase4-agent-layer.md
├── src/
│   ├── datatypes.py              # 共享类型
│   ├── engine/                   # 零 I/O 纯函数
│   │   ├── ledger.py, risk_profile.py, allocation.py
│   │   ├── screener.py, auditor.py, optimizer.py
│   │   ├── stress_tester.py, health_checker.py
│   ├── data/                     # I/O 管线
│   │   ├── market.py, cache.py, portfolio_db.py
│   │   └── sources/ (akshare.py, tiantian.py, eastmoney.py)
│   ├── agent/                    # LangGraph DAG
│   │   ├── state.py, graph.py, signals.py, llm.py
│   │   └── nodes/ (data_collector, debater, allocator, risk_assessor, reporter)
│   ├── redlines/                 # 红线规则 DSL
│   │   ├── hard_rules.py, personal_rules.py
│   └── tools/                    # MCP server + 6 tools
│       ├── server.py, __main__.py
│       ├── risk.py, portfolio.py, advisory.py, audit.py, scenario.py, market.py
├── tests/
│   ├── conftest.py
│   ├── engine/, agent/, data/, redlines/, tools/, integration/
│   └── test_datatypes.py
└── scripts/
    ├── init_db.py, healthcheck.py
```

### 关键架构决策

1. **engine/ 层零 I/O** — 纯函数，接收数据返回结果。所有 I/O 在 data/ 层。测试无需 mock 网络。
2. **Agent DAG 借鉴 TradingAgents 四阶段** — 数据采集→多空辩论→建议→风险评估，但不照搬。适配基金/ETF 多资产组合而非个股。
3. **红线规则分离** — hard_rules（通用，不可关）与 personal_rules（用户配置，可覆盖）
4. **数据隔离** — 每个用户独立 SQLite DB 文件，路径从环境变量或配置获取

---

## 4. 代码风格

### Python 规范

```python
"""模块级 docstring — 简短说明本模块职责。"""
from decimal import Decimal
from typing import Protocol, NamedTuple

# 类型优先 — 所有公共接口有类型标注
class AuditResult(NamedTuple):
    code: str
    passed: bool
    severity: str  # "pass" | "warn" | "reject"
    reasons: list[str]

class AuditorProtocol(Protocol):
    """审计接口 — engine 层不依赖具体数据源。"""
    def audit(self, code: str, planned_amount: Decimal) -> AuditResult: ...

# 金额一律 Decimal，禁止 float
def calculate_fee(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount * rate).quantize(Decimal("0.01"))

# pytest fixtures + parametrize 覆盖边缘
# 测试命名：test_{函数名}_{场景}_{期望}
def test_calculate_fee_zero_rate_returns_zero():
    assert calculate_fee(Decimal("10000"), Decimal("0")) == Decimal("0")
```

### 红线规则 DSL（声明式，非 imperative）

```python
# 好：声明式规则，读规则即读意图
RULE_FUND_MIN_SIZE = RedLine(
    id="RL-001",
    severity="reject",
    condition=lambda f: f.net_asset_value < Decimal("200_000_000"),
    message="基金规模 < 2亿，单客户持仓 ≤ 5万"
)
```

---

## 5. 测试策略

| 层级 | 框架 | 位置 | 覆盖要求 |
|------|------|------|---------|
| 单元测试 | pytest | tests/engine/ | ≥80% 行覆盖 |
| 集成测试 | pytest + mock | tests/agent/ | 每个 DAG 节点≥2场景 |
| 红线规则 | pytest parametrize | tests/redlines/ | 每条规则≥3 case |
| 数据层 | pytest + 本地 SQLite | tests/data/ | 每个 CRUD 操作≥1 case |
| E2E | 独立脚本 | scripts/healthcheck.py | 真实网络调用，手动触发 |

### 测试铁律
- engine/ 层测试不发起网络请求（纯函数）
- 数据层测试使用 mock 数据源（通过依赖注入）
- 金额断言精确到分（`Decimal("0.01")`）
- CI 不跑需要真实 API key 的测试（标记 `@pytest.mark.integration`）

---

## 6. Boundaries

### Always do
- 金额用 `Decimal`，禁止 `float`
- 公共 API 有类型标注
- engine 层零 I/O（纯函数）
- 数据隔离（每个用户独立 DB）
- 网络调用前 `unset http_proxy https_proxy`
- 输出六段式模板（持仓→层级→单品→调整→压测→时序）
- 建议附带免责声明（"不构成投资建议"）

### Ask first
- 新增第三方依赖（pyproject.toml 变更）
- 红线规则修改（影响所有用户）
- 数据库 schema 变更
- 通信协议切换（MCP ↔ A2A）
- 数据源变更（akshare ↔ tushare）
- 安全相关配置（文件权限、密钥存储）

### Never do
- 自动执行交易（永远只做分析建议）
- 推荐个股（仅基金/ETF/指数）
- 提交密钥/Token/密码到 git
- 编辑 vendor/ 或第三方源码
- 删除测试不经确认
- 超过组合 20% 的单品推荐

---

## 7. 迁移策略

从 v0.x (finance_skill) → v2.0 (fortress):

1. **保留并移植：**
   - 9 条红线规则逻辑 → src/redlines/
   - 三层架构 + 四桶模型算法 → src/engine/allocation.py
   - 天天基金/东财 API 适配器 → src/data/sources/
   - 六段式输出模板 → references/
   - 情景压力测试参数 → src/engine/stress_tester.py

2. **丢弃并重写：**
   - 10 个扁平工具（→ Agent DAG 引导式管线）
   - PyPortfolioOpt 集成（→ Riskfolio-Lib）
   - 单体 DB schema（→ 三实体模型 + 多用户隔离）
   - 手动工具调用模式（→ 对话流 + 状态机）

3. **归档：** v0.x repo 保留为 `finance-advisor-v0`，README 顶部加迁移指引

---

## 8. 阶段规划

| 阶段 | 产物 | 预计 |
|------|------|------|
| **Phase 0.5** ✅ | 补充调研（MCP vs A2A、LangGraph 深度评估、akshare 稳定性） | 2026-06-19 完成 |
| **Phase 1** 🔄 | 本 SPEC 确认 + 架构设计文档（docs/architecture.md） | 2026-06-19 进行中 |
| **Phase 2** | 数据层 — 三实体账本 + SQLite + 数据源适配器 | 2-3 sessions |
| **Phase 3** | 引擎层 — 风险测评、筛选、审计、优化、压测 | 2-3 sessions |
| **Phase 4** | Agent 层 — LangGraph DAG + 对话流 | 3-4 sessions |
| **Phase 5** | 红线规则库 — 可配置化 + DSL | 1-2 sessions |
| **Phase 6** | 工具注册 + 双平台适配 | 2-3 sessions |
| **Phase 7** | 测试 + 文档 + E2E 验证 | 2-3 sessions |

---

## Open Questions — ✅ 已决议（Phase 0.5 调研 + Phase 1 确认）

1. **MCP 还是 A2A？** → **MCP。** 堡垒是单 Agent Skill，不需要跨 Agent 协调。A2A 留待未来多 Agent 场景。MCP 生态成熟（10000+ server），Anthropic/OpenAI/Google 均支持。
2. **LangGraph 是否过重？** → **用 LangGraph。** GitHub 调研确认：6/7 高星金融 Agent 项目用 LangGraph（含 TradingAgents 85.8k⭐），FenixAI v2.0 有从 CrewAI→LangGraph 的迁移教训。轻量自研 DAG 迁移成本高于预期。
3. **多用户数据库隔离** → **多 DB 文件。** 每用户独立 SQLite 文件，最简单、最安全、零配置。
4. **前端交互** → **纯对话式 + HTML 报告片段**（对话内渲染）。参考 trading-agents-plugin 做 Claude Code slash command。可选 Web UI 延后。
5. **数据源降级** → **akshare → 天天基金直连 → 本地 SQLite 缓存**三级 fallback。参考 WhenTrade 多源故障转移设计。不支持实时行情（akshare 稳定性不足），仅日频/周频数据。

### 调研依据
- **MCP vs A2A**: [DigitalOcean](https://www.digitalocean.com/community/tutorials/a2a-vs-mcp-ai-agent-protocols), [Cisco](https://blogs.cisco.com/ai/mcp-and-a2a-a-network-engineers-mental-model-for-agentic-ai), [Atlan](https://atlan.com/know/mcp/mcp-vs-a2a-protocol/)
- **LangGraph**: [TradingAgents](https://github.com/TauricResearch/TradingAgents) (85.8k⭐), [FenixAI v2.0](https://github.com/Ganador1/FenixAI_tradingBot), [PrimoAgent](https://github.com/ivebotunac/PrimoAgent), [Langfuse 框架对比](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)
- **akshare**: [Issue #6100](https://github.com/akfamily/akshare/issues/6100), [东财反爬分析](https://blog.gitcode.com/4bc544bb3520ca3789bfc4528e1c2fff.html)

---

*SPEC v1.0 — Phase 1 确认锁定*
