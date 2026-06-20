"""Fortress MCP Server — 6 self-documenting tools for AI investment advisory.

Usage:
    python -m src.tools.server          # stdio transport (MCP clients)
    python src/tools/server.py --sse    # SSE transport (HTTP clients)

Three User Paths:
    A 底仓配置(求确定性): assess_risk → get_allocation → get_advice → run_scenario
    B 机会捕捉(求收益):   get_advice(path=B) → audit_single_fund → run_scenario
    C 持仓诊断(求安心):   get_advice(path=C) → audit_single_fund → run_scenario
"""
from mcp.server.fastmcp import FastMCP

from src.tools.advisory import get_advice as _get_advice
from src.tools.audit import audit_single_fund as _audit_single_fund
from src.tools.market import lookup_fund as _lookup_fund
from src.tools.portfolio import get_allocation as _get_allocation
from src.tools.risk import assess_risk as _assess_risk
from src.tools.scenario import run_scenario as _run_scenario

server = FastMCP("fortress")


# ── Tool 1: Risk Assessment ──────────────────────────────────────────

@server.tool()
def assess_risk(
    horizon: str,
    max_loss_pct: float,
    income: int,
    experience: int,
    liquidity: int,
) -> dict:
    """【路径A第1步】6因子风险测评 → 确定风险等级 + 建议配置比例。

    WHEN TO USE:
    - 新用户首次建立投资组合（路径A的起点）
    - 用户询问"我适合什么风险等级"、"帮我做风险测评"
    - 用户描述了投资期限(A-E)、亏损容忍度(A-E)、收入(A-E)、经验(A-E)、流动性(A-E)时

    HOW TO USE:
    - horizon: 投资期限 — "A"(1年内)|"B"(1-2年)|"C"(2-3年)|"D"(3-5年)|"E"(5年以上)
    - max_loss_pct: 最大可接受亏损%(e.g. 10.0=10%)
    - income: 收入稳定性 A(1)|B(2)|C(3)|D(4)|E(5) — 已转为1-5
    - experience: 投资经验 A(1)|B(2)|C(3)|D(4)|E(5) — 已转为1-5
    - liquidity: 流动性需求 A(1)|B(2)|C(3)|D(4)|E(5) — 已转为1-5
    - 如果用户未明确提供某些参数，根据对话上下文推断合理默认值
    - 结果中的 risk_level 应传递给 get_allocation

    RETURNS: {level, total_score, equity_pct, bond_pct, cash_pct, scores}
    - level: "conservative" | "moderate" | "aggressive"
    - scores: 各因子0-20分，反映风险承受能力
    """
    return _assess_risk(horizon, max_loss_pct, income, experience, liquidity)


# ── Tool 2: Allocation ───────────────────────────────────────────────

@server.tool()
def get_allocation(risk_level: str, total_amount: float) -> dict:
    """【路径A第2步】三层架构+四桶模型 → 生成具体配置方案。

    WHEN TO USE:
    - 已完成风险测评后，生成具体投资分配（路径A的延续）
    - 用户说"我有X万，怎么分配"、"帮我做个配置方案"
    - 需要知道每类资产买多少钱、买什么类型的基金

    HOW TO USE:
    - risk_level: 来自 assess_risk 的返回值，或用户明确表达的风险偏好
    - total_amount: 用户的总投资金额（元）
    - 三层: 活钱(日常开销)→稳健(保值)→增值(长期增长)
    - 四桶: 货币基金、债券基金、混合基金、指数基金

    RETURNS: {equity_pct, bond_pct, cash_pct, total, buckets[]}
    - buckets: 每个桶的 name(名称), amount(金额), fund_type(推荐基金类型), layer(所属层)
    """
    return _get_allocation(risk_level, total_amount)


# ── Tool 3: Advisory Report ──────────────────────────────────────────

@server.tool()
def get_advice(
    path: str,
    message: str,
    equity: float = 0,
    bond: float = 0,
    cash: float = 0,
) -> dict:
    """【全路径通用】运行完整投顾管线，生成HTML分析报告。

    PATHS (三条路径，选其一):
    - A (底仓配置 求确定性): 适合首次配置。先调 assess_risk + get_allocation 再用此工具。
    - B (机会捕捉 求收益): 适合市场出现机会时。会提取多空信号，评估调仓建议。
    - C (持仓诊断 求安心): 适合定期检查。会运行压力测试+健康评分+单品审计。

    WHEN TO USE:
    - 用户说"给我一份完整报告"时
    - 需要汇总展示所有分析结果时
    - 已收集了 portfolio/risk_profile 数据，需要生成最终输出时

    HOW TO USE:
    - 如果用户说"首次配置"，用 path="A"
    - 如果用户问"有没有机会"、"现在该买什么"，用 path="B"
    - 如果用户问"检查下我的持仓"、"组合健康吗"，用 path="C"
    - equity/bond/cash: 当前持仓金额（可选，有就传）

    RETURNS: {report_html, path, errors[]}
    - report_html: 含6段式报告(持仓→风险→配置→审计→压测→健康)的HTML
    - errors: 管线执行中的问题列表
    """
    portfolio = {"equity": equity, "bond": bond, "cash": cash}
    return _get_advice(path, message, portfolio)


# ── Tool 4: Fund Audit ───────────────────────────────────────────────

@server.tool()
def audit_single_fund(
    code: str,
    name: str,
    fund_type: str,
    net_asset_value: float,
    fee_rate: float,
    inception_date: str,
    planned_amount: float,
    total_portfolio: float = 0,
) -> dict:
    """【全路径通用】对单只基金运行5条红线规则审计。

    WHEN TO USE:
    - 用户想买入某基金前（"帮我看看这只基金能不能买"）
    - 持仓诊断时逐只审核（路径C的一部分）
    - 用户询问"为什么不能买XX"时

    5 HARD RULES (不可绕过):
    - RL-001: 规模<2亿 + 持仓>5万 → REJECT
    - RL-002: 成立<1年 → WARN
    - RL-003: 费率>1.5% → WARN
    - RL-004: 单品>组合20% → WARN
    - RL-005: 规模<5亿 + 持仓>2万 → WARN

    HOW TO USE:
    - 用户提供基金代码时，先用 lookup_fund 获取基金信息，再调用此工具审计
    - 如果 total_portfolio>0，会额外检查集中度风险(RL-004)
    - REJECT = 强烈不建议买入，WARN = 注意风险但非禁止

    RETURNS: {fund_code, passed, severity, reasons[]}
    - passed: true=通过审计, false=有警告或被拒绝
    - severity: "pass"|"warn"|"reject"
    - reasons: 触发的具体规则及说明
    """
    return _audit_single_fund(
        code, name, fund_type, net_asset_value, fee_rate,
        inception_date, planned_amount,
        total_portfolio if total_portfolio > 0 else None,
    )


# ── Tool 5: Stress Testing ───────────────────────────────────────────

@server.tool()
def run_scenario(
    equity: float,
    bond: float,
    cash: float,
    scenario_name: str = "",
) -> dict:
    """【全路径通用】用5种历史极端情景对组合进行压力测试。

    AVAILABLE SCENARIOS:
    - "2008 全球金融危机": 股票-50%, 债券+5%
    - "2015 A股暴跌": 股票-40%, 债券+2%
    - "2020 新冠冲击": 股票-30%, 债券+10%
    - "利率大幅上行": 股票-15%, 债券-10%
    - "人民币贬值压力": 股票-10%, 债券-5%

    WHEN TO USE:
    - 配置完成后，回答"最坏情况下会亏多少"（路径A末尾）
    - 市场波动时，评估"如果再来一次2008年会怎样"
    - 定期诊断时，检查组合抗风险能力（路径C）
    - 调仓前对比不同方案的抗压能力

    HOW TO USE:
    - scenario_name 留空 → 自动选对你的组合影响最大的历史情景
    - scenario_name 指定 → 用该情景测试
    - equity/bond/cash: 当前的股票/债券/现金市值（元，非百分比）

    RETURNS: {scenario, total_loss, loss_pct, final_value,
              equity_impact, bond_impact, cash_impact}
    """
    name = scenario_name if scenario_name else None
    return _run_scenario(equity, bond, cash, name)


# ── Tool 6: Market Data ──────────────────────────────────────────────

@server.tool()
def lookup_fund(code: str) -> dict:
    """【前置工具】查询基金基本信息和近期净值（三级数据降级）。

    WHEN TO USE:
    - 审计基金前，先获取基金信息（audit_single_fund 需要这些参数）
    - 用户询问"XX基金怎么样"时，获取基本信息
    - 需要查看基金净值走势时

    DATA SOURCE FALLBACK:
    - 主源: akshare (中国基金数据)
    - 备源: 天天基金 / eastmoney API
    - 兜底: 本地SQLite缓存(24h TTL)

    RETURNS: {code, name, type, net_asset_value, fee_rate,
              inception_date, recent_nav[]}
    - 如果所有数据源失败，返回 {error, code}

    ⚠️ 基金代码格式: 中国基金为6位数字，如"000001"
    """
    return _lookup_fund(code)


# ── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run()
