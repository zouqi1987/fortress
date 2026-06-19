"""MCP tool: market data lookup."""
from datetime import date, timedelta
from decimal import Decimal

from src.data.cache import MarketCache
from src.data.market import CachedSource, MarketDataFacade
from src.data.sources.akshare import AKShareSource
from src.data.sources.eastmoney import EastmoneySource
from src.data.sources.tiantian import TiantianSource


def lookup_fund(code: str) -> dict:
    """Look up fund information and recent NAV.

    Args:
        code: fund code (e.g. "000001")

    Returns fund info dict or error message.
    """
    try:
        # Build the full failover chain
        facade = MarketDataFacade([AKShareSource(), TiantianSource(), EastmoneySource()])

        end = date.today()
        start = end - timedelta(days=30)

        info = facade.fetch_fund_info(code)
        navs = facade.fetch_fund_nav(code, start, end)

        return {
            "code": info.code,
            "name": info.name,
            "type": info.type,
            "net_asset_value": float(info.net_asset_value),
            "fee_rate": float(info.fee_rate),
            "inception_date": info.inception_date.isoformat(),
            "recent_nav": [
                {"date": n.date.isoformat(), "nav": float(n.nav), "acc_nav": float(n.acc_nav)}
                for n in navs[-5:]  # last 5 days
            ],
        }
    except Exception as e:
        return {"error": str(e), "code": code}
