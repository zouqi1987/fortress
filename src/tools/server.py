"""Fortress MCP Server — 16 tools across 3 named Agents + 13 supporting tools.

Usage:
    python -m src.tools.server          # stdio transport (MCP clients)
    python src/tools/server.py --sse    # SSE transport (HTTP clients)

Three Named Agents (one-click entry points):
    底仓配置(求确定性): allocate_portfolio  → 风险测评 → 资产配置 → 压力测试
    机会捕捉(求收益):   hunt_opportunity    → 市场周期研判 → 基金筛选 → 多空信号
    持仓诊断(求安心):   diagnose_holdings   → 健康评分 → 红线审计 → 压力测试

Thirteen Supporting Tools:
    assess_risk, get_allocation, get_advice (legacy), screen_funds,
    audit_single_fund, run_scenario, lookup_fund, lookup_index,
    check_health, detect_regime, list_hard_rules, manage_personal_rules,
    export_report
"""
from mcp.server.fastmcp import FastMCP

from src.tools.advisory import allocate_portfolio as _allocate_portfolio
from src.tools.advisory import diagnose_holdings as _diagnose_holdings
from src.tools.advisory import get_advice as _get_advice
from src.tools.advisory import hunt_opportunity as _hunt_opportunity
from src.tools.audit import audit_single_fund as _audit_single_fund
from src.tools.export import export_report as _export_report
from src.tools.health import check_health as _check_health
from src.tools.macro import detect_regime as _detect_regime
from src.tools.market import lookup_fund as _lookup_fund
from src.tools.market import lookup_index as _lookup_index
from src.tools.personal_rules import manage_personal_rules as _manage_personal_rules
from src.tools.screener import screen_funds as _screen_funds
from src.tools.portfolio import get_allocation as _get_allocation
from src.tools.risk import assess_risk as _assess_risk
from src.tools.rules import list_hard_rules as _list_hard_rules
from src.tools.scenario import run_scenario as _run_scenario

from src.logging_config import setup as setup_logging

# Configure structured logging — all output to stderr
setup_logging()

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


# ── Agent 1: 底仓配置 (Path A) ─────────────────────────────────────────

@server.tool(name="底仓配置")
def allocate_portfolio(
    message: str,
    equity: float = 0,
    bond: float = 0,
    cash: float = 0,
) -> dict:
    """【路径A】底仓配置Agent — 完整的首次投资组合建立流程。

    执行流程:
      数据收集 → 风险测评 → 资产配置 → 压力测试 → HTML报告

    使用场景:
    - "我想开始理财了，帮我做个配置"
    - "帮我评估一下风险承受能力"
    - "首次买基金，应该怎么分配"

    HOW TO USE:
    - message: 描述你的财务情况、投资目标、风险偏好等（必填）
    - equity/bond/cash: 当前持仓金额，默认0（可选）

    RETURNS: {report_html, path, errors[]}
    """
    return _allocate_portfolio(message, equity, bond, cash)


# ── Agent 2: 机会捕捉 (Path B) ─────────────────────────────────────────

@server.tool(name="机会捕捉")
def hunt_opportunity(
    message: str,
    equity: float = 0,
    bond: float = 0,
    cash: float = 0,
) -> dict:
    """【路径B】机会捕捉Agent — 市场机会识别与调仓建议。

    执行流程:
      数据收集 → 市场周期研判 → 多空信号提取 → 基金筛选 → 配置建议 → HTML报告

    使用场景:
    - "大盘跌了很多，现在是不是抄底的机会"
    - "最近有什么好的投资机会"
    - "帮我看看现在该加仓还是减仓"

    HOW TO USE:
    - message: 描述你关注的市场、板块或基金类型（必填）
    - equity/bond/cash: 当前持仓金额（可选）

    RETURNS: {report_html, path, errors[]}
    """
    return _hunt_opportunity(message, equity, bond, cash)


# ── Agent 3: 持仓诊断 (Path C) ─────────────────────────────────────────

@server.tool(name="持仓诊断")
def diagnose_holdings(
    message: str,
    equity: float = 0,
    bond: float = 0,
    cash: float = 0,
) -> dict:
    """【路径C】持仓诊断Agent — 投资组合健康检查与风险排查。

    执行流程:
      数据收集 → 四维健康评分 → 单品红线审计 → 压力测试 → HTML报告

    使用场景:
    - "帮我检查下现在的持仓健不健康"
    - "最近跌了不少，帮我看看组合有没有问题"
    - "定期体检一下我的基金持仓"

    HOW TO USE:
    - message: 描述你的持仓情况和担忧（必填）
    - equity/bond/cash: 当前持仓金额（可选，有就传）

    RETURNS: {report_html, path, errors[]}
    """
    return _diagnose_holdings(message, equity, bond, cash)


# ── Tool 7: Fund Audit ───────────────────────────────────────────────

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


# ── Tool 8: Stress Testing ───────────────────────────────────────────

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


# ── Tool 9: Market Data ──────────────────────────────────────────────

@server.tool()
def lookup_fund(code: str, start: str = "", end: str = "") -> dict:
    """【前置工具】查询基金基本信息和近期净值（三级数据降级）。

    WHEN TO USE:
    - 审计基金前，先获取基金信息（audit_single_fund 需要这些参数）
    - 用户询问"XX基金怎么样"时，获取基本信息
    - 需要查看基金净值走势时

    DATA SOURCE FALLBACK:
    - 主源: akshare (中国基金数据)
    - 备源: 天天基金 / eastmoney API
    - 兜底: 本地SQLite缓存(24h TTL)

    HOW TO USE:
    - start/end: 可选，净值历史区间 "YYYY-MM-DD"。留空默认近30天。

    RETURNS: {code, name, type, net_asset_value, fee_rate,
              inception_date, date_range, recent_nav[], data_source[, cached_at, stale_warning]}
    - data_source: "akshare"|"tiantian"|"cache" — 实际数据来源
    - stale_warning: 若 data_source="cache"，包含缓存时间的中文警告
    - ⚠️ 必须检查 data_source！若为 "cache"，务必向用户明确告知：
      "当前数据来自{缓存时间}的本地缓存，非实时数据。建议稍后重试获取最新行情。"
    - 如果所有数据源失败，返回 {error, code}

    ⚠️ 基金代码格式: 中国基金为6位数字，如"000001"
    """
    return _lookup_fund(code, start, end)


# ── Tool 10: Index Data ────────────────────────────────────────────────

@server.tool()
def lookup_index(code: str, start: str = "", end: str = "") -> dict:
    """查询指数日线数据（如上证指数、深证成指）。

    WHEN TO USE:
    - 用户问"最近大盘怎么样"、"上证指数走势如何"
    - detect_regime 前获取指数数据和均线
    - 市场分析需要指数历史数据

    DATA SOURCE FALLBACK:
    - 主源: akshare
    - 备源: eastmoney
    - 兜底: 本地SQLite缓存(24h TTL)

    HOW TO USE:
    - code: 指数代码，如 "000001" (上证指数), "399001" (深证成指)
    - start/end: 可选，日期区间 "YYYY-MM-DD"。留空默认近90天。

    RETURNS: {code, date_range, count, data[{date, close, volume}], data_source[, stale_warning]}
    - data_source: "akshare"|"eastmoney"|"cache" — 实际数据来源
    - stale_warning: 若 data_source="cache"，包含缓存时间的中文警告
    - ⚠️ 必须检查 data_source！若为 "cache"，务必向用户明确告知数据来自缓存及缓存时间。
    """
    return _lookup_index(code, start, end)


# ── Tool 11: Hard Rules ────────────────────────────────────────────────

@server.tool()
def list_hard_rules() -> dict:
    """列出全部5条硬红线规则的ID、严重程度和说明。

    WHEN TO USE:
    - 用户问"有哪些红线规则"、"硬性限制是什么"
    - 审计前了解规则定义
    - 向用户解释为什么某基金被拒绝

    5 HARD RULES:
    - RL-001 (REJECT): 基金规模 < 2亿 且 持仓 > 5万
    - RL-002 (WARN): 基金成立不足1年
    - RL-003 (WARN): 管理费率超过 1.5%
    - RL-004 (WARN): 单只基金占组合比例超过 20%
    - RL-005 (WARN): 基金规模 < 5亿 且 持仓 > 2万

    RETURNS: {count, rules[{id, severity, message}]}
    """
    return _list_hard_rules()


# ── Tool 12: Portfolio Health ─────────────────────────────────────────

@server.tool()
def check_health(
    equity_pct: int,
    bond_pct: int,
    cash_pct: int,
    risk_level: str,
    fee_ratio: float,
    max_drawdown_pct: float,
    num_holdings: int,
) -> dict:
    """【全路径通用】四维度组合健康度评分：偏离度 + 分散度 + 费率 + 回撤。

    WHEN TO USE:
    - 用户问"我的组合健康吗"、"帮我检查下持仓健康度"
    - 定期诊断时独立触发（无需跑完整 get_advice 管线）
    - 调仓后验证组合改善程度

    FOUR DIMENSIONS:
    - drift_score (0-35): 当前配置偏离风险目标的程度
    - diversification_score (0-30): 持仓数量是否在理想范围(4-8只)
    - fee_score (0-25): 加权费率评分
    - drawdown_score (0-10): 近期最大回撤评分

    HOW TO USE:
    - equity_pct/bond_pct/cash_pct: 当前配置百分比，三项之和应为100
    - risk_level: "conservative" | "moderate" | "aggressive"
    - fee_ratio: 加权平均费率 (e.g. 0.012 = 1.2%)
    - max_drawdown_pct: 近期最大回撤 (e.g. 15.0 = 15%)
    - num_holdings: 持仓基金数量

    RETURNS: {overall_score, grade, drift_score, diversification_score,
              fee_score, drawdown_score, warnings[]}
    - grade: "A"(>=80) | "B"(>=60) | "C"(>=40) | "D"(>=20) | "F"(<20)
    """
    return _check_health(
        equity_pct, bond_pct, cash_pct, risk_level,
        fee_ratio, max_drawdown_pct, num_holdings,
    )


# ── Tool 13: Market Regime ───────────────────────────────────────────

@server.tool()
def detect_regime(
    current: float | None = None,
    ma200: float | None = None,
    ma120: float | None = None,
    risk_level: str = "",
) -> dict:
    """检测当前市场周期（牛/熊/震荡）及宏观风险乘数。

    COMPARES index level vs 200-day and 120-day moving averages:
    - BULL: 指数 > MA200 → 乘数 1.0（标准配置）
    - SIDEWAYS: MA120 < 指数 < MA200 → 乘数 0.8（略保守）
    - BEAR: 指数 < MA120 → 乘数 0.6（保守，偏债券）

    WHEN TO USE:
    - 用户问"现在是什么市场周期"、"当前市场是牛还是熊"
    - 调仓前评估宏观环境
    - 结合风险等级计算配置调整乘数

    HOW TO USE:
    - current: 当前指数点位（如上证指数）。无数据时默认 SIDEWAYS。
    - ma200/ma120: 移动平均线。可通过 lookup_index 获取历史数据后自行计算。
    - risk_level: 若提供，同时返回该风险等级下的配置乘数。

    RETURNS: {regime, description[, multiplier]}
    - regime: "bull" | "bear" | "sideways"
    - multiplier: 0.6-1.0，应用于股票配置比例
    """
    return _detect_regime(current, ma200, ma120, risk_level)


# ── Tool 14: Personal Rules ──────────────────────────────────────────

@server.tool()
def manage_personal_rules(
    action: str,
    rule_id: str = "",
    description: str = "",
    fund_types_blacklist: str = "",
    max_single_position: float | None = None,
    min_fund_size: float | None = None,
) -> dict:
    """管理个人投资红线规则：增/删/查/清。

    Personal rules supplement hard rules — users define their own constraints.

    WHEN TO USE:
    - 用户说"我不投股票型基金"、"单只基金最多10万"
    - 用户想查看或修改自己的个性化限制
    - 配置风险偏好后的补充约束

    ACTIONS:
    - "list": 列出所有活跃个人规则
    - "add": 添加规则。需 rule_id + 至少一项约束。
    - "remove": 删除规则。需 rule_id。
    - "clear": 清空所有个人规则。

    HOW TO USE (add):
    - fund_types_blacklist: 逗号分隔，如 "stock,mixed" 表示不投股票和混合型
    - max_single_position: 单只基金持仓上限（元）
    - min_fund_size: 最低基金规模要求（元），如 500000000 表示不低于5亿

    RETURNS: 依 action 不同返回 {active_count, rules[]} 或 {status, message}
    """
    return _manage_personal_rules(
        action, rule_id, description, fund_types_blacklist,
        max_single_position, min_fund_size,
    )


# ── Tool 15: Fund Screening ───────────────────────────────────────────

@server.tool()
def screen_funds(
    funds: list,
    min_net_asset_value: float = 0,
    allowed_types: str = "",
    max_fee_rate: float = 0.03,
    risk_level: str = "",
) -> dict:
    """筛选并评分基金列表 — 统一 5 维度加权评分。

    5 dimensions: 机构共识 / 同类业绩 / 风控 / 持续性 / 费率
    每维度 0-100,按基金类型(主动/被动/货币) × 风险画像 加权。

    WHEN TO USE:
    - 用户问"哪些基金最好"、"帮我选基金"
    - 拿到 lookup_fund 结果后，做横向比较
    - 配置方案确定后，筛选具体产品

    HOW TO USE:
    - funds: 基金信息列表，每项含 code, name, type, net_asset_value, fee_rate, inception_date
    - min_net_asset_value: 最低规模过滤（元），默认0不过滤
    - allowed_types: 逗号分隔，如 "bond,mixed"，空=全部
    - max_fee_rate: 最高可接受费率，默认 0.03 (3%)
    - risk_level: "conservative"|"moderate"|"aggressive"，空=moderate

    RETURNS: {count, results[{code, name, type, score, dimension_breakdown, warnings[]}]}
    - results 按 score 降序排列
    """
    return _screen_funds(funds, min_net_asset_value, allowed_types, max_fee_rate, risk_level)


# ── Tool 16: Report Export ───────────────────────────────────────────

@server.tool()
def export_report(
    report_html: str,
    output_path: str,
    title: str = "投资分析报告",
) -> dict:
    """【全路径通用】将 HTML 报告保存为自包含 .html 文件（浏览器打开后 Ctrl+P 打印为 PDF）。

    使用场景:
    - "把这份报告保存下来发给我客户"
    - "导出为 PDF 文件"

    HOW TO USE:
    - report_html: get_advice / Agent 工具返回的 HTML 报告内容
    - output_path: 保存路径（如 "/home/user/报告.html" 或 "report.html"）
    - title: 页面标题，默认 "投资分析报告"

    RETURNS: {file_path, size_bytes, message}
    - file_path: 文件的绝对路径
    - size_bytes: 文件大小（字节）
    - message: 用户可读的保存确认消息
    """
    return _export_report(report_html, output_path, title)


# ── Entry Point ──────────────────────────────────────────────────────


def _startup_data_check():
    """Check NAV data completeness on startup. Auto-backfill if incomplete.

    Finance principle: any data gap could cause wrong investment decisions.
    Checks latest NAV date vs latest trading date; if gap exists, triggers
    update() which auto-backfills as needed.
    """
    import os
    import sys
    from src.data.sources.nav_store import NavStore

    db_path = os.path.join(
        os.environ.get("FORTRESS_DATA_DIR", "data"),
        "market_cache.db",
    )
    try:
        store = NavStore(db_path)
        report = store.update()
        store.close()

        if report.action == "current":
            print(f"[startup] NAV data up to date ({report.latest_db_date})",
                  file=sys.stderr)
        elif report.action == "bulk_update":
            print(f"[startup] NAV data updated: +{report.points_added} points "
                  f"(gap={report.gap_days}d)", file=sys.stderr)
        elif report.action == "recovery_mode":
            print(f"[startup] NAV data in recovery mode (gap={report.gap_days}d), "
                  f"lazy per-fund fetch enabled", file=sys.stderr)
        elif report.action == "auto_backfill_completed":
            print(f"[startup] NAV auto-backfill completed: "
                  f"{report.funds_updated} funds, {report.points_added} points "
                  f"(gap was {report.gap_days}d)", file=sys.stderr)
    except Exception as e:
        print(f"[startup] NAV data check failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    _startup_data_check()
    server.run()
