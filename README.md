# 🏰 Fortress — AI 投资顾问 v2.0

对话式 AI 投资顾问 Agent Skill。三条路径：

- **路径 A — 底仓配置**（求确定性）：风险测评 → 三层架构 → 产品筛选 → 压力测试
- **路径 B — 机会捕捉**（求收益）：市场异动 → 多空辩论 → 调仓建议
- **路径 C — 持仓诊断**（求安心）：拉取持仓 → 层级偏离 → 单品审计 → 健康评分

## 快速开始

```bash
# 安装
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# E2E 健康检查
python scripts/healthcheck.py

# 初始化数据库
python scripts/init_db.py data/portfolio.db
```

## 架构

```
src/
├── engine/     # 核心引擎（零 I/O 纯函数）
├── data/       # 数据层（SQLite + 数据源适配器）
├── agent/      # LangGraph DAG（5 节点，3 路径）
├── redlines/   # 红线规则 DSL（hard + personal）
├── tools/      # MCP 工具注册（6 工具）
└── datatypes.py # 共享数据类型
```

## MCP 工具

| 工具 | 功能 |
|------|------|
| `assess_risk` | 5 因子风险测评 |
| `get_allocation` | 三层架构配置方案 |
| `get_advice` | 完整投顾报告 |
| `audit_single_fund` | 单品红线审计 |
| `run_scenario` | 情景压力测试 |
| `lookup_fund` | 基金数据查询 |

## 测试

```bash
pytest tests/ -v --cov=src          # 全部测试 + 覆盖率
pytest tests/ -v -k "not integration"  # 跳过需要网络的测试
```

## 约束

- `engine/` 零 I/O — 所有引擎模块纯函数
- 所有金额 `Decimal`，禁止 `float`
- 永不自动交易，永不推荐个股
- 每用户独立 SQLite 数据库

## 免责声明

本工具不构成投资建议。所有分析仅供参考，投资决策由用户自行做出。
