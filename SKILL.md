# Fortress — AI 投资顾问 Agent Skill

对话式 AI 投资顾问。三条路径：底仓配置（求确定性）+ 机会捕捉（求收益）+ 持仓诊断（求安心）。

## 支持平台

- **Claude Code**: MCP 协议，6 个工具
- **Hermes Agent**: A2A 适配（待实现）

## MCP 工具

| 工具 | 功能 |
|------|------|
| `assess_risk` | 5 因子风险测评 |
| `get_allocation` | 三层架构配置方案 |
| `get_advice` | 完整投顾报告（路径 A/B/C） |
| `audit_single_fund` | 单品红线审计 |
| `run_scenario` | 情景压力测试 |
| `lookup_fund` | 基金数据查询 |

## 红线规则

- **Hard Rules**: 5 条系统规则，不可关闭（规模/成立时间/费率/集中度/小基金持仓）
- **Personal Rules**: 用户可配置偏好（基金类型黑名单/单只上限/最小规模）

## 免责声明

本 Skill 不构成投资建议。所有分析仅供参考，投资决策由用户自行做出。永不自动执行交易，永不推荐个股。
