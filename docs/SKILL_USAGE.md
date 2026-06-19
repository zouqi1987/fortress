# Fortress Skill 使用手册

> 覆盖所有使用场景 | v2.0 | 2026-06-20

## 目录

1. [快速入门](#1-快速入门)
2. [路径 A: 底仓配置](#2-路径-a-底仓配置)
3. [路径 B: 机会捕捉](#3-路径-b-机会捕捉)
4. [路径 C: 持仓诊断](#4-路径-c-持仓诊断)
5. [独立工具使用](#5-独立工具使用)
6. [红线规则与审计](#6-红线规则与审计)
7. [高级场景](#7-高级场景)
8. [故障排查](#8-故障排查)

---

## 1. 快速入门

### Claude Code

```text
# 无需任何配置。在项目目录下启动 Claude Code，.mcp.json 自动发现。
# 直接对话即可：

用户: 用 fortress 帮我做风险测评
用户: fortress 给50万做个配置方案
用户: 审计下基金 000001，计划买5万
```

### Hermes Agent

```yaml
# ~/.hermes/config.yaml 添加：
mcp_servers:
  fortress:
    command: /path/to/fortress/.venv/bin/python
    args: [-m, src.tools.server]
    env: {FORTRESS_DATA_DIR: /path/to/fortress/data}
    enabled: true
```

```text
# Hermes 对话：
用户: 用 fortress 帮我分析投资组合
```

---

## 2. 路径 A: 底仓配置

> 新用户首次建立投资组合。风险测评 → 三层架构 → 产品筛选 → 压力测试

### 场景 2.1: 保守型投资者

```text
用户: 我刚工作两年，有20万闲钱想做投资。偏好低风险，最多能接受10%的亏损。
      收入不算特别稳定，投资经验不多，可能需要保持一定流动性。

Claude 自动调用 assess_risk:
  → horizon="medium", max_loss_pct=10, income=2, experience=2, liquidity=4
  → 结果: CONSERVATIVE, 总分24, 建议股票10%/债券60%/现金30%

然后调用 get_allocation:
  → risk_level="conservative", total_amount=200000
  → 活钱60000(货币基金) + 稳健100000(债券/混合) + 增值40000(指数/债券)

然后调用 get_advice:
  → path="A", 生成完整 HTML 报告
```

**预期输出**: 保守型配置方案，强调债券为主（60%），活钱充足（30%），增值有限（10%）。含压力测试结果。

### 场景 2.2: 激进型投资者

```text
用户: 我有50万，想做长期投资至少5年。能接受30%甚至更多的回撤。
      收入很稳定，自己有5年以上投资经验，不需要留太多现金。

Claude 调用 assess_risk:
  → horizon="long", max_loss_pct=30, income=5, experience=5, liquidity=1
  → 结果: AGGRESSIVE, 总分~90, 建议股票80%/债券15%/现金5%

然后调用 get_allocation:
  → risk_level="aggressive", total_amount=500000
  → 活钱50000(货币) + 稳健175000(债券/混合) + 增值275000(指数/债券)
```

### 场景 2.3: 流动性需求高

```text
用户: 100万投资，但我可能随时需要用钱。只能接受5%的亏损。

Claude 分析: liquidity_need=5 → 大量配置货币基金
  → 活钱占比最高，增值几乎为0
  → 压力测试显示最坏情况下损失有限
```

---

## 3. 路径 B: 机会捕捉

> 市场出现机会时，提取多空信号，评估是否调仓。

### 场景 3.1: 关注特定板块机会

```text
用户: 最近医药板块跌了很多，我想看看有没有机会。我关注了000001(华夏成长)
      和001234(某医药基金)。我当前持仓: 股票型50000, 债券型100000, 现金30000。

Claude 调用 get_advice(path="B"):
  → debater node 提取信号: PE分位、波动率、分散度
  → 返回多空信号 + 综合判断框架

信号示例输出:
  🟢 多方:
    - 数据覆盖: 2只基金 — 已覆盖关注基金的基本面数据
    - 估值水平: PE 12.0 — 处于历史偏低区间，估值有支撑
    - 分散度: 3只持仓 — 分散度适中
  
  🔴 空方:
    - 分散度: 3只持仓 — 集中度偏高，建议分散至5-8只
  
  ⚖️ 综合判断: 偏多（多方2条 > 空方1条）
```

### 场景 3.2: 无关注市场，纯咨询

```text
用户: 现在适合加仓吗？我的组合是60%股票/30%债券/10%现金。

Claude 调用 get_advice(path="B"):
  → 没有 market_data 时，debater 返回错误提示
  → 但 risk_assessor 和 reporter 仍正常工作
  → 输出: 当前持仓诊断 + 压力测试结果
```

---

## 4. 路径 C: 持仓诊断

> 定期检查持仓健康度。层级偏离 → 单品审计 → 压力测试 → 健康评分。

### 场景 4.1: 季度例行诊断

```text
用户: 帮我检查下我的投资组合健康度。
      股票70000, 债券20000, 现金10000。
      持有: 000001(华夏成长)50000, 000003(债基稳健)20000。

Claude 调用 get_advice(path="C"):
  → risk_assessor: 最坏情景压测 (2008金融危机, -28.5%)
  → health_check: 四维评分
    - 配置偏离: 当前E70/B20/C10 vs 目标取决于风险等级
    - 分散度: 2只持仓 → 偏低
    - 费率效率: 加权费率计算
    - 回撤控制: 近期最大回撤评估
  → 等级: B (≥60) 或 C (≥40)
```

### 场景 4.2: 大跌后诊断

```text
用户: 上周跌了好多，我想看看我的组合现在什么情况。
      股票40000(原来60000), 债券28000, 现金10000。

Claude 分析:
  → 自动选择最坏历史情景做压力测试
  → 根据当前权益/债券/现金比例评估健康度
  → 如果偏离目标配置，建议再平衡
```

---

## 5. 独立工具使用

### 5.1 assess_risk — 风险测评

```text
用户: fortress assess_risk horizon=long max_loss_pct=20 income=4 experience=3 liquidity=2

返回:
  level: "aggressive"
  total_score: 76
  equity_pct: 80
  bond_pct: 15
  cash_pct: 5
  scores: {horizon: 18, loss_tolerance: 12, income_stability: 15, experience: 10, liquidity: 15}
```

参数说明:

| 参数 | 类型 | 可选值 |
|------|------|--------|
| horizon | string | "short" (≤1年), "medium" (1-3年), "long" (≥3年) |
| max_loss_pct | float | 可接受的最大亏损百分比 |
| income | int (1-5) | 1=非常不稳定, 5=非常稳定 |
| experience | int (1-5) | 投资经验 |
| liquidity | int (1-5) | 1=低流动性需求, 5=随时需要资金 |

### 5.2 get_allocation — 配置方案

```text
用户: fortress get_allocation risk_level=moderate total_amount=500000

返回:
  equity_pct: 38
  bond_pct: 40
  cash_pct: 22
  total: 500000
  buckets:
    - {name: "活钱-货币基金", amount: 100000, fund_type: "money"}
    - {name: "稳健-债券基金", amount: 135000, fund_type: "bond"}
    - {name: "稳健-混合基金", amount: 90000, fund_type: "mixed"}
    - {name: "增值-指数基金", amount: 122500, fund_type: "index"}
    - {name: "增值-债券基金", amount: 52500, fund_type: "bond"}
```

### 5.3 get_advice — 完整报告

```text
用户: fortress get_advice path=A message="首次配置50万" equity=0 bond=0 cash=500000

返回: HTML 格式的完整分析报告，含:
  1. 当前持仓表
  2. 风险测评结果
  3. 配置方案（含各桶金额）
  4. 单品审计（如有持仓）
  5. 压力测试结果
  6. 组合健康评分
  7. 免责声明
```

### 5.4 audit_single_fund — 基金审计

```text
用户: fortress audit_single_fund code=000001 name="华夏成长" fund_type=mixed
      net_asset_value=5000000000 fee_rate=0.01 inception_date=2010-06-01
      planned_amount=50000 total_portfolio=500000

返回:
  fund_code: "000001"
  passed: true
  severity: "pass"
  reasons: []
```

触发红线:
```text
用户: fortress audit_single_fund code=000099 name="迷你基金" fund_type=stock
      net_asset_value=100000000 fee_rate=0.025 inception_date=2026-01-01
      planned_amount=200000 total_portfolio=500000

返回:
  fund_code: "000099"
  passed: false
  severity: "reject"
  reasons: [
    "基金规模 1.0亿 < 2亿，单客户持仓不得超过5万 (计划 20万)",
    "基金成立不足1年",
    "费率 2.50% 超过 1.5%",
    "单品集中度 40% 超过 20% 上限"
  ]
```

### 5.5 run_scenario — 压力测试

```text
# 默认最坏历史情景
用户: fortress run_scenario equity=300000 bond=150000 cash=50000
  → 自动选择 2008全球金融危机 (-50%股票/+5%债券)

# 指定情景
用户: fortress run_scenario equity=300000 bond=150000 cash=50000 scenario_name="2015 A股暴跌"
  → 使用 2015年A股暴跌 (-40%股票/+2%债券)

返回:
  scenario: "2008 全球金融危机"
  total_loss: -142500
  loss_pct: -0.285
  final_value: 357500
  equity_impact: -150000
  bond_impact: 7500
  cash_impact: 0
```

可用情景: "2008 全球金融危机", "2015 A股暴跌", "2020 新冠冲击", "利率大幅上行", "人民币贬值压力"

### 5.6 lookup_fund — 基金数据查询

```text
用户: fortress lookup_fund code=000001

返回:
  code: "000001"
  name: "华夏成长混合"
  type: "mixed"
  net_asset_value: 5000000000
  fee_rate: 0.01
  inception_date: "2001-12-18"
  recent_nav: [
    {date: "2026-06-15", nav: 1.287, acc_nav: 3.456},
    ...
  ]

# 查询失败时:
  {error: "All sources failed", code: "000001"}
```

---

## 6. 红线规则与审计

### 6.1 五条 Hard Rules

| ID | 规则 | 严重度 | 触发条件 |
|----|------|--------|---------|
| RL-001 | 规模风险 | REJECT | 规模<2亿 且 持仓>5万 |
| RL-002 | 成立时间 | WARN | 成立<1年 |
| RL-003 | 费率风险 | WARN | 费率>1.5% |
| RL-004 | 集中度 | WARN | 单品>组合20% |
| RL-005 | 中等规模 | WARN | 规模<5亿 且 持仓>2万 |

### 6.2 Personal Rules（用户偏好）

```text
用户: 我不投资股票型基金
Claude: (设置 personal_rule fund_types_blacklist={"stock"})
        以后审计时自动 reject 股票型基金

用户: 单只基金最多10万
Claude: (设置 personal_rule max_single_position=100000)
        以后审计时检查金额是否超标
```

---

## 7. 高级场景

### 7.1 多工具组合使用

```text
用户: 我有100万想做投资。先帮我做风险测评，然后给配置方案。

Claude (自动编排):
  1. assess_risk(horizon="medium", max_loss_pct=15, income=4, experience=3, liquidity=3)
     → MODERATE, E60/B30/C10
  
  2. get_allocation(risk_level="moderate", total_amount=1000000)
     → 5个桶的具体分配
  
  3. run_scenario(equity=600000, bond=300000, cash=100000)
     → 2008金融危机: 损失 -28.5%, 最终 715000
  
  4. get_advice(path="A", ...)
     → 完整报告
```

### 7.2 再平衡建议

```text
用户: 我的持仓是80%股票/10%债券/10%现金，但我的风险等级是moderate。
      需要再平衡吗？

Claude:
  1. 对比当前配置 vs 目标配置 (moderate: E60/B30/C10)
  2. 偏离度: |80-60| + |10-30| + |10-10| = 40 → 严重偏离
  3. 建议: 卖出20%股票，买入20%债券
```

### 7.3 新基金申购前审核

```text
用户: 我想申购 000002(迷你基金)，计划买20万。帮我审核一下。

Claude 调用 audit_single_fund:
  → RL-001 触发: 规模<2亿 且 持仓>5万 → REJECT
  → 不建议买入。建议考虑同类型但规模更大的替代基金。
```

### 7.4 市场异动分析

```text
用户: 今天A股跌了3%，我的基金组合受影响了吗？

Claude:
  1. lookup_fund 获取最新净值
  2. run_scenario 模拟当前组合在类似冲击下的表现
  3. 对比情景 "2015 A股暴跌" (-40%股票)
  4. 当前冲击3% → 在可控范围内
```

---

## 8. 故障排查

### 工具不可用

```text
症状: "fortress 工具未注册"
解决: 
  - Claude Code: /reload-plugins
  - Hermes: 检查 ~/.hermes/config.yaml 中 mcp_servers.fortress 配置
  - 验证: python -m src.tools.server (应启动 stdio 模式等待输入)
```

### 数据源不可用

```text
症状: lookup_fund 返回 error
原因: akshare API 不稳定（已知问题）
降级:
  1. akshare → 自动重试 3 次
  2. tiantian/eastmoney → 自动重试 2 次
  3. 本地缓存 → 返回24小时内的数据
  4. 全部失败 → 返回 error dict（不阻塞流程）
```

### 红线规则误报

```text
症状: 正常基金被误判为违规
解决: 查看具体 reasons 字段，检查触发条件
      如果是 personal_rules 导致，对话中调整偏好即可
      如果是 hard_rules 触发，规则不可跳过 — 这是安全约束
```

---

*手册版本: 1.0 | 堡垒 v2.0*
