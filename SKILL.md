# Fortress — AI 投资顾问 Agent Skill

对话式 AI 投资顾问。三条路径：底仓配置（求确定性）+ 机会捕捉（求收益）+ 持仓诊断（求安心）。

## 架构理念

**堡垒 = 领域计算引擎。宿主 LLM = 自然语言叙事者。**

- Skill 负责量化计算：PE 分位、波动率、规模阈值、红线规则、压力测试
- 宿主 LLM（Claude Code）负责理解意图 + 包装结果为自然语言
- **不需要独立的 API key**

## 支持平台

- **Claude Code**: MCP 协议，6 个工具，自动发现 `.mcp.json`
- **Hermes Agent**: 待适配

## MCP 工具

| 工具 | 功能 | 输入 |
|------|------|------|
| `assess_risk` | 5 因子风险测评 | horizon, max_loss, income, experience, liquidity |
| `get_allocation` | 三层架构配置方案 | risk_level, total_amount |
| `get_advice` | 完整投顾报告（路径 A/B/C） | path, message, equity?, bond?, cash? |
| `audit_single_fund` | 单品红线审计 | code, name, type, size, fee, inception, amount |
| `run_scenario` | 情景压力测试 | equity, bond, cash, scenario_name? |
| `lookup_fund` | 基金数据查询（三级降级） | code |

## 红线规则

- **Hard Rules (5条)**: 规模/成立时间/费率/集中度/小基金持仓 — 不可关闭
- **Personal Rules**: 用户可配置偏好 — 类型黑名单/单只上限

## 使用方式

```bash
# 安装
pip install -e ".[dev]"

# 测试
pytest tests/ -v

# 启动 MCP server
python -m src.tools.server

# Claude Code 自动发现 .mcp.json → 对话中调用
```

## 免责声明

本 Skill 不构成投资建议。所有分析仅供参考。永不自动执行交易，永不推荐个股。
