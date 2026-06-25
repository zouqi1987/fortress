# 🏰 Fortress — AI 投资顾问 Agent Skill

[![Test](https://github.com/zouqi1987/fortress/actions/workflows/test.yml/badge.svg)](https://github.com/zouqi1987/fortress/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/zouqi1987/fortress/blob/main/LICENSE)

对话式 AI 投资顾问 **Claude Code Skill**。3 个命名 Agent + 16 个 MCP 工具：
- **底仓配置**（求确定性）：风险测评 → 三层架构 → 产品筛选 → 压���测试
- **机会捕捉**（求收益）：市场异动 → 多空信号 → 调仓建议
- **持仓诊断**（求安心）：拉取持仓 → 层级偏离 → 单品审计 → 健康评分

> **架构理念**: 堡垒是**领域计算引擎**。宿主 LLM（Claude Code）负责自然语言叙事，堡垒负责量化信号计算。不需要独立的 API key。

---

## 作为 Skill 使用

### 1. 安装

```bash
# 方式 A: Claude Plugin（推荐）
claude plugin add /path/to/fortress

# 方式 B: 手动安装
git clone https://github.com/zouqi1987/fortress.git
cd fortress
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Claude Code 自动发现

Claude Code 启动时自动加载项目根目录的 `.mcp.json`，注册 16 个 MCP 工具（3 个 Agent + 13 个支持工具）。无需额外配置。

验证工具已注册：
```
/reload-plugins
```

### 3. 开始对话

直接在对话中说：

> "用 fortress 帮我做风险测评，我计划投3年，能接受15%亏损，
>  收入稳定，有3年经验，资金流动性需求中等"

> "用 fortress 给50万做个资产配置方案"

> "帮我审计下这只基金：华夏成长000001，计划买5万"

Claude 会自动调用对应的 MCP 工具完成计算并返回分析结果。

### 4. 可用工具

| 工具 | 功能 | 示例输入 |
|------|------|---------|
| `assess_risk` | 5 因子风险测评 | horizon="medium", max_loss_pct=15, income=4, experience=3, liquidity=3 |
| `get_allocation` | 三层架构配置方案 | risk_level="moderate", total_amount=500000 |
| `get_advice` | 完整投顾报告（路径 A/B/C） | path="A", message="首次配置50万", equity=0, bond=0, cash=500000 |
| `audit_single_fund` | 单品红线审计 | code="000001", planned_amount=50000 |
| `run_scenario` | 情景压力测试 | equity=300000, bond=150000, cash=50000 |
| `lookup_fund` | 基金数据查询（三级降级） | code="000001" |

---

## 平台兼容性

| 平台 | 状态 | 协议 |
|------|------|------|
| **Claude Code** | ✅ 已验证 | MCP（Model Context Protocol） |
| **Hermes Agent** | ⚠️ 待适配 | A2A（Agent-to-Agent） |

Fortress 核心引擎（engine/ + data/ + agent/）是协议无关的纯 Python。`src/tools/` 层当前为 MCP 实现。适配 Hermes 需要编写 A2A adapter（约 200 行），将 6 个工具函数包装为 A2A Task 接口。引擎代码无需修改。

---

## 架构

```
宿主 LLM (Claude Code)
    │  MCP 协议
    ▼
src/tools/      # MCP server + 6 tool wrappers
    │
    ▼
src/agent/      # LangGraph DAG（5 节点，3 路径）+ 信号引擎
    │
    ├── src/engine/   # 核心引擎（零 I/O 纯函数，Decimal 计算）
    └── src/data/     # 数据层（SQLite + 数据源适配器 + 缓存）
```

---

## 开发

```bash
# 运行测试
pytest tests/ -v

# 跳过网络测试
pytest tests/ -v -k "not integration"

# E2E 健康检查
python scripts/healthcheck.py

# 初始化数据库
python scripts/init_db.py data/portfolio.db

# 启动 MCP server（调试用）
python -m src.tools.server
```

## 约束

- `engine/` 零 I/O — 所有引擎模块纯函数
- 所有金额 `Decimal`，禁止 `float`
- 永不自动交易，永不推荐个股
- 每用户独立 SQLite 数据库

## 免责声明

本 Skill 不构成投资建议。所有分析仅供参考，投资决策由用户自行做出。
