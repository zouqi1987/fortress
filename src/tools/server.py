"""Fortress MCP Server — registers 6 tools via FastMCP.

Usage:
    python -m src.tools.server          # stdio transport (for MCP clients)
    python src/tools/server.py --sse    # SSE transport (for HTTP clients)
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
    """5-factor risk profile assessment.

    Args:
        horizon: Investment horizon — 'short', 'medium', or 'long'
        max_loss_pct: Maximum acceptable loss percentage (e.g. 15.0 = 15%)
        income: Income stability 1-5 (1=unstable, 5=very stable)
        experience: Investment experience 1-5 (1=novice, 5=professional)
        liquidity: Liquidity need 1-5 (1=low, 5=high)
    """
    return _assess_risk(horizon, max_loss_pct, income, experience, liquidity)


# ── Tool 2: Allocation ───────────────────────────────────────────────

@server.tool()
def get_allocation(risk_level: str, total_amount: float) -> dict:
    """Build 3-layer allocation plan for a given risk level.

    Args:
        risk_level: 'conservative', 'moderate', or 'aggressive'
        total_amount: Total investable amount in CNY
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
    """Run the full advisory pipeline and return an HTML report.

    Args:
        path: 'A' (底仓配置), 'B' (机会捕捉), or 'C' (持仓诊断)
        message: User's question or context
        equity: Equity amount in CNY (optional)
        bond: Bond amount in CNY (optional)
        cash: Cash amount in CNY (optional)
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
    """Audit a single fund against redline rules.

    Args:
        code: Fund code (e.g. '000001')
        name: Fund name
        fund_type: 'stock', 'bond', 'mixed', 'index', or 'money'
        net_asset_value: Fund size in CNY
        fee_rate: Annual fee rate (e.g. 0.015 = 1.5%)
        inception_date: Fund inception date (YYYY-MM-DD)
        planned_amount: Planned investment amount in CNY
        total_portfolio: Total portfolio value for concentration check
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
    """Stress test portfolio against historical or named scenario.

    Args:
        equity: Equity amount in CNY
        bond: Bond amount in CNY
        cash: Cash amount in CNY
        scenario_name: Name of historical scenario, or '' for worst-case
    """
    name = scenario_name if scenario_name else None
    return _run_scenario(equity, bond, cash, name)


# ── Tool 6: Market Data ──────────────────────────────────────────────

@server.tool()
def lookup_fund(code: str) -> dict:
    """Look up fund info and recent NAV from market data sources.

    Uses three-level fallback: akshare → tiantian → local cache.

    Args:
        code: Fund code (e.g. '000001')
    """
    return _lookup_fund(code)


# ── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run()
