# Fortress — AI 投资顾问 Agent Skill

对话式 AI 投资顾问。3 个命名 Agent + 16 个 MCP 工具，覆盖个人基金投资全场景。

## 安装

```bash
# Claude Code — 本地添加
claude plugin add /path/to/fortress

# Claude Code — 从 Marketplace 安装（已发布后）
claude plugin install fortress

# Hermes Agent — 在 ~/.hermes/config.yaml 中添加 local skill
```

## 架构理念

**堡垒 = 领域计算引擎。宿主 LLM = 自然语言叙事者。**

- Skill 负责量化计算：PE 分位、波动率、规模阈值、红线规则、压力测试
- 宿主 LLM（Claude Code / Hermes）负责理解意图 + 包装结果为自然语言
- **不需要独立的 API key**

## 支持平台

- **Claude Code**: MCP 协议 + Claude Plugin，自动发现 `.mcp.json`（生产就绪）
- **Hermes Agent**: A2A 协议，Agent Card 自动发现（实验性）

## 3 个命名 Agent（一键入口）

| Agent | 路径 | 描述 | 使用场景 |
|-------|------|------|----------|
| `底仓配置` | A | 风险测评 → 资产配置 → 压力测试 | "帮我做个配置"、"评估风险" |
| `机会捕捉` | B | 市场研判 → 基金筛选 → 多空信号 | "有没有机会"、"该加仓吗" |
| `持仓诊断` | C | 健康评分 → 红线审计 → 压力测试 | "帮我看看持仓"、"体检一下" |

## MCP 工具（16个：3 Agent + 13 支持）

### 路径 A 核心链 — 底仓配置

| 工具 | 功能 | 关键输入 |
|------|------|---------|
| `assess_risk` | 6 因子风险测评 → 等级 + 建议配置比 | horizon, max_loss_pct, income, experience, liquidity |
| `get_allocation` | 三层四桶配置方案 → 具体金额分配 | risk_level, total_amount |
| `screen_funds` | 基金筛选评分（5 维度加权） | funds[], allowed_types, risk_level? |
| `get_advice` | 完整投顾管线 → HTML 报告 | path="A", message, equity?, bond?, cash? |

### 路径 B 核心链 — 机会捕捉

| 工具 | 功能 | 关键输入 |
|------|------|---------|
| `lookup_index` | 指数日线数据（上证/深证等） | code, start?, end? |
| `detect_regime` | 市场周期检测 + 宏观乘数 | current?, ma200?, ma120?, risk_level? |
| `lookup_fund` | 基金信息 + 净值历史（三级降级） | code, start?, end? |
| `audit_single_fund` | 单品 5 条红线审计 | code, name, type, size, fee, inception, amount |

### 路径 C 核心链 — 持仓诊断

| 工具 | 功能 | 关键输入 |
|------|------|---------|
| `check_health` | 四维度健康评分（偏离/分散/费率/回撤） | equity_pct, bond_pct, cash_pct, risk_level, fee_ratio, max_drawdown_pct, num_holdings |
| `run_scenario` | 5 种历史极端情景压力测试 | equity, bond, cash, scenario_name? |

### 全路径通用

| 工具 | 功能 | 关键输入 |
|------|------|---------|
| `list_hard_rules` | 查看 5 条硬红线规则定义 | （无参数） |
| `manage_personal_rules` | 管理个人投资规则（增/删/查/清） | action, rule_id?, fund_types_blacklist?, max_single_position? |

## 典型使用场景

### 场景 1：新用户首次配置（路径 A）

> 用户："我工作三年，有 20 万闲钱想投资，能接受 10% 亏损，帮我做个方案。"

```
1. assess_risk("C", 10.0, 3, 3, 3)
   → risk_level="moderate", equity_pct=60, bond_pct=30, cash_pct=10

2. get_allocation("moderate", 200000)
   → buckets: 活钱 20,000(货币) + 稳健 60,000(债券) + 增值 120,000(混合+指数)

3. lookup_fund("000001") + lookup_fund("000002") ...  // 查找候选基金
   → 每只基金的 code, name, type, size, fee, inception, NAV

4. screen_funds([
     {code:"000001", name:"华夏成长", type:"mixed", ...},
     {code:"000002", name:"易方达债券", type:"bond", ...},
   ], allowed_types="mixed,bond")
   → results 按 score 降序，选出每桶最优基金

5. get_advice("A", "首次配置20万")
   → HTML 报告：持仓→风险→配置→审计→压测→健康

6. run_scenario(120000, 60000, 20000)
   → "2008金融危机"下最大亏损 -63,000 (-31.5%)
```

### 场景 2：市场机会评估（路径 B）

> 用户："最近大盘跌了不少，现在适合加仓吗？我 60% 股票 + 30% 债券 + 10% 现金。"

```
1. lookup_index("000001", start="2026-01-01")
   → 上证指数近半年日线数据 [{date, close, volume}, ...]

2. 计算 MA200/MA120（由 LLM 根据 index data 自行计算）
   detect_regime(current=3050, ma200=3200, ma120=3100, risk_level="moderate")
   → regime="bear", multiplier=0.6  ← 熊市，建议减配股票

3. lookup_fund("000001")  // 查找想加仓的基金
   → 基金基本信息和近期净值

4. screen_funds([fundA, fundB, fundC], allowed_types="mixed,bond")
   → 筛选出当前环境下较优的基金

5. get_advice("B", "市场下跌，要不要加仓", equity=120000, bond=60000, cash=20000)
   → 多空辩论 → 配置建议 → 压力测试 → HTML 报告

6. audit_single_fund(...)  // 对拟买入基金逐只审计
   → 确认不触发 RL-001~RL-005
```

### 场景 3：定期持仓诊断（路径 C）

> 用户："季度检查，帮我看看现在组合健康吗。股票 8 万、债券 3 万、现金 1 万，共 5 只基金。"

```
1. get_advice("C", "季度诊断", equity=80000, bond=30000, cash=10000)
   → HTML 报告：压力测试 + 健康评分 + 单品审计

2. check_health(67, 25, 8, "moderate", 0.012, 12.0, 5)
   → overall_score=72, grade="B"
   → drift_score=28 (股票67% vs 目标60%, 偏离7%)

3. audit_single_fund("000001", "华夏成长", "mixed", 5e9, 0.010, "2010-06-01", 30000, 120000)
   → passed=true, severity="pass"
   // 逐只审计全部 5 只持仓

4. run_scenario(80000, 30000, 10000)
   → worst_scenario="2015 A股暴跌", total_loss=-33,500

5. list_hard_rules()  // 确认是否触发新规则
6. manage_personal_rules("list")  // 检查个人规则是否需调整
```

## 个人规则配置场景

> 用户："我不投股票型基金。另外单只基金最多 5 万。"

```
1. manage_personal_rules("add", rule_id="PR-001",
     description="不投股票型", fund_types_blacklist="stock")

2. manage_personal_rules("add", rule_id="PR-002",
     description="单只上限5万", max_single_position=50000)

3. manage_personal_rules("list")
   → active_count=2, rules=[{id:"PR-001", ...}, {id:"PR-002", ...}]
```

## 红线规则

- **Hard Rules (5条)**: RL-001 规模<2亿+持仓>5万(REJECT), RL-002 成立<1年(WARN), RL-003 费率>1.5%(WARN), RL-004 单品>组合20%(WARN), RL-005 规模<5亿+持仓>2万(WARN) — 不可关闭
- **Personal Rules**: 用户可配置 — 类型黑名单/单只上限/最低规模，通过 `manage_personal_rules` 管理

## 数据架构

```
akshare (主源, 3次指数退避)
  → tiantian / eastmoney (备源, 2次重试)
    → SQLite 本地缓存 (兜底, 24h TTL)
```

## 使用方式

```bash
# 安装
pip install -e ".[dev]"

# 测试（281 通过）
pytest tests/ -v

# 启动 MCP server (stdio)
python -m src.tools.server

# 启动 MCP server (SSE)
python src/tools/server.py --sse

# Claude Code 自动发现 .mcp.json → 对话中调用
# Hermes Agent 配置 mcp_servers 后自动发现
```

## 关键约束

- engine/ 层零 I/O 纯函数，全 `decimal.Decimal` 金额
- 永不自动交易，永不推荐个股
- 所有数据来自实时 API，不硬编码

## 免责声明

本 Skill 不构成投资建议。所有分析仅供参考。永不自动执行交易，永不推荐个股。
