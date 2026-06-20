# Fortress 项目说明文档

> AI 投资顾问 Claude Code Skill | 2026-06-20

## 目录

1. [项目概述](#1-项目概述)
2. [功能清单](#2-功能清单)
3. [系统架构](#3-系统架构)
4. [核心模块详解](#4-核心模块详解)
5. [安装与使用](#5-安装与使用)
6. [开发指南](#6-开发指南)
7. [测试策略](#7-测试策略)
8. [红线规则](#8-红线规则)
9. [数据源与降级策略](#9-数据源与降级策略)
10. [约束与边界](#10-约束与边界)

---

## 1. 项目概述

Fortress 是一个 **Claude Code Agent Skill**，通过 MCP (Model Context Protocol) 协议为宿主 LLM 提供量化投资分析能力。

### 架构理念

```text
用户 → 宿主 LLM 理解意图 → MCP 调用 fortress 工具 → 引擎计算 → 结构化信号返回 → 宿主 LLM 叙事
```

- **堡垒 = 领域计算引擎**（纯函数、零 I/O、Decimal 精度）
- **宿主 LLM = 自然语言叙事者**（理解意图、包装结果）
- **不需要独立的 API key** — 宿主 LLM 自带语言能力

### 三条用户路径

| 路径 | 名字 | 目标 | 流程 |
|------|------|------|------|
| A | 底仓配置 | 求确定性 | 风险测评 → 三层架构 → 产品筛选 → 压力测试 → 配置方案 |
| B | 机会捕捉 | 求收益 | 市场数据 → 多空信号提取 → 调仓建议 |
| C | 持仓诊断 | 求安心 | 拉取持仓 → 层级偏离检查 → 单品审计 → 健康评分 → 诊断报告 |

---

## 2. 功能清单

### 2.1 MCP 工具（6 个）

| 工具 | 功能 | 输入参数 |
|------|------|---------|
| `assess_risk` | 6 因子风险测评 | horizon, max_loss_pct, income(1-5), experience(1-5), liquidity(1-5) |
| `get_allocation` | 三层架构 + 四桶模型配置 | risk_level, total_amount |
| `get_advice` | 完整投顾报告 | path(A/B/C), message, equity?, bond?, cash? |
| `audit_single_fund` | 单品红线审计 | code, name, type, size, fee, inception, amount, portfolio? |
| `run_scenario` | 历史情景压力测试 | equity, bond, cash, scenario_name? |
| `lookup_fund` | 基金数据查询（三级降级） | code |

### 2.2 引擎计算能力

| 引擎 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `risk_profile` | 6 因子风险评分 | 问卷答案 | RiskProfile + 建议配置比例 |
| `allocation` | 三层架构分配 | RiskLevel + 总金额 | AllocationPlan（含 Bucket） |
| `screener` | 基金筛选排名 | FundInfo[] + 条件 | 筛选结果（评分 + 警告） |
| `auditor` | 单品红线审计 | FundInfo + 金额 | pass/warn/reject |
| `optimizer` | Riskfolio-Lib 组合优化 | 收益率序列 | 最优权重 |
| `stress_tester` | 5 种历史情景压测 | 组合配置 | 各资产损失 + 最终价值 |
| `health_checker` | 四维健康评分 | 组合指标 | A-F 等级 + 维度分数 |

### 2.3 数据能力

- **GnuCash 三实体账本**: Account / Transaction / Split + 延迟约束校验
- **SQLite 持久化**: 每用户独立 DB，Decimal 精度存储
- **三级数据降级**: akshare → 天天基金/eastmoney → 本地 SQLite 缓存
- **TTL 缓存**: 基金净值 24h，基金信息 7d，指数行情 24h

### 2.4 红线规则

- **5 条 Hard Rules**: 规模/成立时间/费率/集中度/小基金持仓（不可关闭）
- **Personal Rules**: 用户可配置（类型黑名单、单只上限、最小规模）

---

## 3. 系统架构

### 分层架构

```text
┌─────────────────────────────────────────┐
│              宿主 LLM                    │
│    Claude Code (MCP) / Hermes (A2A)     │
├─────────────────────────────────────────┤
│  src/tools/     MCP Server + 6 工具     │
├─────────────────────────────────────────┤
│  src/agent/     LangGraph DAG + 信号引擎  │
│       ├── nodes/  5 个节点              │
│       ├── signals.py  结构化信号提取     │
│       └── graph.py  路径路由 A/B/C       │
├─────────────────────────────────────────┤
│  src/engine/    核心引擎（零 I/O 纯函数） │
│  src/data/      数据层（SQLite + 适配器） │
│  src/redlines/  红线规则 DSL             │
│  src/datatypes.py  共享类型              │
└─────────────────────────────────────────┘
```

### 依赖方向

```text
tools/ → agent/ → engine/ + data/
              └── datatypes.py（叶子模块）
```

- `engine/` 只依赖 `datatypes.py`（stdlib + Decimal + 共享类型）
- `data/` 依赖 `engine/`（持久化引擎类型）+ `datatypes.py`
- `agent/` 依赖 `engine/` + `data/`（编排层）
- `tools/` 依赖 `engine/` + `data/` + `agent/`（集成层）

### 文件清单（22 个模块）

```text
src/
├── datatypes.py                 # FundInfo, NAVPoint, IndexPoint, fmt_amount, classify_fund_type
├── engine/
│   ├── ledger.py                # Account, Transaction, Split, validate_transaction
│   ├── risk_profile.py          # 6 因子风险测评
│   ├── allocation.py            # 三层架构 + 四桶模型
│   ├── screener.py              # 基金筛选排名
│   ├── auditor.py               # 单品审计（5 条红线规则）
│   ├── optimizer.py             # Riskfolio-Lib 组合优化
│   ├── stress_tester.py         # 情景压力测试（5 种历史情景）
│   └── health_checker.py        # 四维健康评分
├── data/
│   ├── market.py                # MarketDataSource Protocol + Facade + CachedSource
│   ├── cache.py                 # SQLite TTL 缓存
│   ├── portfolio_db.py          # 三实体账本 CRUD
│   └── sources/
│       ├── _eastmoney_base.py   # 东财 API 共享逻辑
│       ├── akshare.py           # AKShare 适配器（主源，3 次指数退避重试）
│       ├── tiantian.py          # 天天基金适配器（备源，2 次重试）
│       └── eastmoney.py         # 东财适配器（备源，指数数据）
├── agent/
│   ├── state.py                 # ConversationState TypedDict
│   ├── graph.py                 # LangGraph DAG（路径 A/B/C 路由）
│   ├── signals.py               # 结构化信号提取（纯计算，零 LLM）
│   ├── llm.py                   # 可选独立 LLM 适配器（FORTRESS_LLM=deepseek）
│   └── nodes/
│       ├── data_collector.py    # 数据采集节点
│       ├── debater.py           # 多空信号提取节点
│       ├── allocator.py         # 配置建议节点
│       ├── risk_assessor.py     # 风险评估节点
│       └── reporter.py          # HTML 报告生成节点
├── redlines/
│   ├── hard_rules.py            # 5 条系统红线规则（不可关闭）
│   └── personal_rules.py        # 用户可配置偏好规则
└── tools/
    ├── server.py                # FastMCP Server（6 个 @server.tool() 装饰器）
    ├── __main__.py              # python -m src.tools.server 入口
    ├── risk.py                  # assess_risk 工具
    ├── portfolio.py             # get_allocation 工具
    ├── advisory.py              # get_advice 工具
    ├── audit.py                 # audit_single_fund 工具
    ├── scenario.py              # run_scenario 工具
    ├── market.py                # lookup_fund 工具
    └── a2a_adapter.py           # A2A 适配器骨架（Hermes 兼容，待 SDK）
```

---

## 4. 核心模块详解

### 4.1 三实体账本 (engine/ledger.py)

采用 GnuCash 24 年工业验证的三实体模型：

```python
Account     # 账户：path="assets:funds:000001", type=ASSET, commodity="000001"
Transaction # 交易：id, date, description, splits (≥2)
Split       # 分录：account_path, amount (借正贷负)

# 延迟约束校验（后置 Scrub，适应脏数据）
validate_transaction(txn) -> list[Violation]
# 检查: ≥2 splits, 合计=0, 无零金额分录
```

### 4.2 6 因子风险测评 (engine/risk_profile.py)

| 因子 | 权重 | 评分逻辑 |
|------|------|---------|
| 投资期限 | 0-20 | A(1年内)=2, B(1-2年)=6, C(2-3年)=10, D(3-5年)=14, E(5年+)=18 |
| 最大亏损容忍 | 0-20 | 5%→3, 10%→8, 15%→12, 25%+→18 |
| 收入稳定性 | 0-20 | (1-5) × 5 |
| 投资经验 | 0-20 | (1-5) × 5 |
| 流动性需求 | 0-20 | 逆映射 (5-n) × 5 |
| 期望收益校验 | — | 5 条一致性规则（高产低险、短投激进、新手激进等） |

- 总分 <30: CONSERVATIVE (股票 10% / 债券 60% / 现金 30%)
- 总分 30-69: MODERATE (股票 40-60% / 债券 30-50% / 现金 10%)
- 总分 ≥70: AGGRESSIVE (股票 75-80% / 债券 15-20% / 现金 5%)

### 4.3 三层架构 + 四桶模型 (engine/allocation.py)

**三层**（中国财富管理标准）:
- **活钱**: 日常开销，随时可取（货币基金）
- **稳健**: 保本为主，稳健增值（债券 + 混合基金）
- **增值**: 长期增值（指数 + 债券基金）

**四桶**（全球资产配置标准）:
- 现金管理 → 货币基金
- 固收 → 债券基金
- 权益 → 指数基金
- 另类 → （暂未启用）

**层级权重**（按风险等级动态调整）:

| 风险等级 | 活钱 | 稳健 | 增值 |
|---------|------|------|------|
| CONSERVATIVE | 30% | 50% | 20% |
| MODERATE | 20% | 45% | 35% |
| AGGRESSIVE | 10% | 35% | 55% |

### 4.4 基金筛选引擎 (engine/screener.py)

**硬筛选条件**（不通过直接排除）:
- 基金规模 ≥ 最小阈值
- 基金类型在白名单内
- 成立时间 ≥ 最小日期
- 费率 ≤ 最大费率

**评分体系（0-100）**:
- 规模得分 (0-30): 越大越好，上限 100 亿
- 成立时长 (0-20): 越久越好，每半年 +0.5
- 费率得分 (0-25): 越低越好，0.5%→25, 2.0%+→5
- 类型加成 (0-15): bond→15, mixed→12, index→10, stock→8, money→5

### 4.5 单品审计引擎 (engine/auditor.py)

| 规则 ID | 条件 | 严重度 |
|---------|------|--------|
| RL-001 | 规模<2亿 且 持仓>5万 | REJECT |
| RL-002 | 成立<1年 | WARN |
| RL-003 | 费率>1.5% | WARN |
| RL-004 | 单品>组合20% | WARN |
| RL-005 | 规模<5亿 且 持仓>2万 | WARN |

### 4.6 压力测试引擎 (engine/stress_tester.py)

5 种历史情景：

| 情景 | 股票冲击 | 债券冲击 |
|------|---------|---------|
| 2008 全球金融危机 | -50% | +5% |
| 2015 A股暴跌 | -40% | +2% |
| 2020 新冠冲击 | -30% | +10% |
| 利率大幅上行 | -15% | -10% |
| 人民币贬值压力 | -10% | -5% |

`worst_scenario_for(portfolio)` — 按总组合影响选择最坏情景。

### 4.7 健康评分引擎 (engine/health_checker.py)

四维评分（各 0-35/0-30/0-25/0-10 = 总分 0-100）:

| 维度 | 分值 | 评分依据 |
|------|------|---------|
| 配置偏离 | 0-35 | 当前配置 vs 目标配置的偏离度 |
| 分散度 | 0-30 | 持仓数量（4-8 最优） |
| 费率效率 | 0-25 | 加权平均费率 |
| 回撤控制 | 0-10 | 最大回撤幅度 |

等级: A(≥80) / B(≥60) / C(≥40) / D(≥20) / F(<20)

### 4.8 信号引擎 (agent/signals.py)

纯计算、零 LLM 调用的结构化信号提取：

```python
@dataclass
class Signal:
    name: str           # "PE分位", "波动率", "资金流向"
    value: str          # "28%", "32%", "+3.2亿"
    interpretation: str # 人类可读解释
    direction: str      # "bull" | "bear"

@dataclass 
class DebateSignals:
    bull_signals: list[Signal]
    bear_signals: list[Signal]
    conclusion_framework: str  # 综合判断框架
```

**信号来源**（全量化计算）:
- 数据覆盖: 已覆盖基金数量 → bull
- 波动率评估: >30%→bear, ≤30%→bull
- PE 估值: <15→bull, >30→bear
- 分散度: 4-8→bull, <3→bear, >12→bear

宿主 LLM 接收这些信号后，用自己的语言渲染成自然语言多空辩论。

---

## 5. 安装与使用

### 5.1 环境要求

- Python 3.12+
- macOS / Linux

### 5.2 安装

```bash
git clone <repo-url> fortress
cd fortress
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 5.3 平台兼容

| 平台 | 协议 | 状态 | 配置方式 |
|------|------|------|---------|
| **Claude Code** | MCP | ✅ 生产就绪 | `.mcp.json` 自动发现 |
| **Hermes Agent** | MCP | ✅ 生产就绪 | `~/.hermes/config.yaml` |
| **A2A Agents** | A2A | ⚠️ 实验性 | `python -m src.tools.a2a_adapter` |

Fortress 核心引擎（engine/ + data/ + agent/）协议无关。适配层仅需 ~50 行。

### 5.4 作为 Claude Code Skill 使用

**自动发现**: Claude Code 启动时自动加载项目根目录的 `.mcp.json`。

```bash
# 1. 进入项目目录
cd fortress

# 2. 启动 Claude Code
claude

# 3. 重载插件（如果已启动）
/reload-plugins

# 4. 直接对话使用
# "用 fortress 帮我做风险测评，计划投3年，接受15%亏损，收入稳定，3年经验，流动性中等"
# "用 fortress 给50万做个资产配置方案"
# "用 fortress 审计基金 000001，计划买5万"
```

### 5.5 作为 Hermes Agent Skill 使用

Hermes Agent 内置 MCP 客户端，可直接连接 fortress MCP server。

**配置** — 编辑 `~/.hermes/config.yaml`：

```yaml
mcp_servers:
  fortress:
    command: /path/to/fortress/.venv/bin/python
    args:
    - -m
    - src.tools.server
    env:
      FORTRESS_DATA_DIR: /path/to/fortress/data
    enabled: true
```

**使用** — 在 Hermes 对话中直接说：
> "用 fortress 帮我分析投资组合，做风险测评"
> "fortress assess_risk horizon=medium max_loss_pct=15 income=4 experience=3 liquidity=3"

Hermes 会自动发现 fortress 的 6 个 MCP 工具。

### 5.6 命令行使用

```bash
# 运行全部测试
pytest tests/ -v

# 跳过网络测试
pytest tests/ -v -k "not integration"

# E2E 健康检查
python scripts/healthcheck.py

# 初始化数据库
python scripts/init_db.py data/portfolio.db

# 启动 MCP server（调试）
python -m src.tools.server
```

---

## 6. 开发指南

### 6.1 代码规范

- **engine/ 零 I/O**: 不导入 logging、不读写文件、不发起网络请求
- **Decimal 金额**: 禁止 float 参与金额计算；仅显示层可用 float 格式化
- **类型标注**: 所有公共函数/方法有完整类型注解
- **frozen dataclass**: 所有 DTO 不可变
- **声明式规则**: 红线规则用 `RedLine(id, severity, condition, message)` 格式

### 6.2 添加新工具

1. 在 `src/tools/` 创建工具函数（调用 engine/ 层）
2. 在 `src/tools/server.py` 添加 `@server.tool()` 装饰器
3. 在 `tests/tools/test_tools.py` 添加测试
4. MCP schema 从 type hints 自动生成

### 6.3 添加新红线规则

```python
# src/redlines/hard_rules.py
HARD_RULES.append(RedLine(
    id="RL-006",
    severity=Severity.WARN,
    condition=lambda f, amount, total: your_condition,
    message="规则描述",
))
```

---

## 7. 测试策略

| 层级 | 位置 | 框架 | 覆盖目标 |
|------|------|------|---------|
| 单元测试 | tests/engine/ | pytest + parametrize | ≥80% |
| 集成测试 | tests/agent/ | pytest + mock | 每节点≥2场景 |
| 红线规则 | tests/redlines/ | pytest parametrize | 每规则≥3 case |
| 数据层 | tests/data/ | pytest + SQLite | 每 CRUD≥1 |
| 工具层 | tests/tools/ | pytest + mock | 每工具≥3 |
| E2E | tests/integration/ | pytest + xfail | 真实 API（手动触发） |
| 健康检查 | scripts/healthcheck.py | — | 全管线 12 项 |

**铁律**:
- engine/ 测试不发起网络请求
- 金额断言精确到 `Decimal("0.01")`
- CI 不跑需要真实 API key 的测试（标记 `@pytest.mark.integration`）

### 测试统计

```text
240 unit tests passed
14 integration tests deselected (CI-safe)
9 integration tests xfailed (documented API instability)
1 integration test skipped (needs API key)
Coverage: 75% (engine 96%, agent 95%, tools 83%)
```

---

## 8. 红线规则

### 8.1 Hard Rules（不可关闭）

```text
RL-001: 基金规模 < 2亿 → 单客户持仓 ≤ 5万元        [REJECT]
RL-002: 基金成立 < 1年 → 缺乏历史业绩                [WARN]
RL-003: 管理费率 > 1.5% → 侵蚀长期收益               [WARN]
RL-004: 单品 > 组合 20% → 集中度风险                  [WARN]
RL-005: 基金规模 < 5亿 → 建议持仓 ≤ 2万元            [WARN]
```

### 8.2 Personal Rules（用户可配置）

```python
PersonalRule(
    id="PREF-001",
    description="不投资股票型基金",
    fund_types_blacklist={"stock"},
)
PersonalRule(
    id="PREF-002",
    description="单只基金上限 10 万",
    max_single_position=Decimal("100000"),
)
```

---

## 9. 数据源与降级策略

### 9.1 三级降级链

```text
1. AKShareSource（主源）
   ├─ 3 次指数退避重试 (1s / 2s / 4s)
   ├─ 调用间隔 ≥2s
   └─ 失败 → 下一级

2. TiantianSource / EastmoneySource（备源）
   ├─ 2 次重试
   ├─ 直连 eastmoney API
   └─ 失败 → 下一级

3. CachedSource（兜底）
   ├─ SQLite TTL 缓存
   ├─ 命中 → 返回
   └─ 未命中 → 报告不可用
```

### 9.2 缓存策略

| 数据类型 | TTL |
|---------|-----|
| 基金净值（日频） | 24 小时 |
| 基金信息 | 7 天 |
| 指数行情（日频） | 24 小时 |

### 9.3 已知限制

- akshare 东财 API 在 2025-2026 年反爬升级，稳定性下降
- 不适合实时行情监控
- 全市场批量分析受限（频率限制）
- 仅支持中国基金/ETF 市场

---

## 10. 约束与边界

### Always Do
- 金额用 `Decimal`，禁止 `float`
- 公共 API 有类型标注
- engine 层零 I/O（纯函数）
- 数据隔离（每用户独立 SQLite）
- 建议附带免责声明

### Ask First
- 新增第三方依赖
- 红线规则修改
- 数据库 schema 变更
- 通信协议切换（MCP ↔ A2A）
- 数据源变更（akshare ↔ tushare）

### Never Do
- 自动执行交易
- 推荐个股（仅基金/ETF/指数）
- 提交密钥/Token/密码到 git
- 超过组合 20% 的单品推荐
- 删除测试不经确认

### 免责声明

> 本 Skill 不构成投资建议。所有分析仅供参考，投资决策由用户自行做出。
> 永不自动执行交易，永不推荐个股。

---

*最后更新: 2026-06-20*
