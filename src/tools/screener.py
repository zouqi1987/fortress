"""MCP tool: fund screening and ranking."""
from datetime import date
from decimal import Decimal
from typing import Any

from src.datatypes import FundInfo
from src.engine.screener import ScreenConfig, screen_funds as _screen


def screen_funds(
    funds: list,
    min_net_asset_value: float = 0,
    allowed_types: str = "",
    max_fee_rate: float = 0.03,
    nav_data: dict | None = None,
) -> dict:
    """Screen and rank a list of funds. v1 static scoring default; v2 when nav_data provided.

    Args:
        funds: List of fund dicts, each with:
            code, name, type, net_asset_value, fee_rate, inception_date ("YYYY-MM-DD").
        min_net_asset_value: Minimum fund size filter (CNY). 0 = no filter.
        allowed_types: Comma-separated fund types, e.g. "bond,mixed". Empty = all.
        max_fee_rate: Maximum acceptable fee rate (e.g. 0.015 = 1.5%).
        nav_data: Optional {code: [nav_values]} for v2 5-dimension scoring.
    """
    if not funds:
        return {"results": [], "count": 0}

    # Build FundInfo list
    fund_infos: list[FundInfo] = []
    errors: list[dict] = []
    for i, f in enumerate(funds):
        try:
            fund_infos.append(FundInfo(
                code=str(f["code"]),
                name=str(f.get("name", "")),
                type=str(f.get("type", "mixed")),
                net_asset_value=Decimal(str(f.get("net_asset_value", 0))),
                fee_rate=Decimal(str(f.get("fee_rate", 0.015))),
                inception_date=date.fromisoformat(str(f.get("inception_date", "2020-01-01"))),
            ))
        except (KeyError, ValueError, TypeError) as e:
            errors.append({"index": i, "fund": f.get("code", "?"), "error": str(e)})

    if not fund_infos:
        return {"results": [], "count": 0, "errors": errors}

    # Build ScreenConfig
    types_set = frozenset(
        t.strip() for t in allowed_types.split(",") if t.strip()
    ) if allowed_types else frozenset({"stock", "bond", "mixed", "index", "money"})

    config = ScreenConfig(
        min_net_asset_value=Decimal(str(min_net_asset_value)),
        allowed_types=types_set,
        max_fee_rate=Decimal(str(max_fee_rate)),
    )

    # Run screening
    results = _screen(fund_infos, config, nav_data)

    return {
        "count": len(results),
        "results": [
            {
                "code": r.fund.code,
                "name": r.fund.name,
                "type": r.fund.type,
                "net_asset_value": float(r.fund.net_asset_value),
                "fee_rate": float(r.fund.fee_rate),
                "inception_date": r.fund.inception_date.isoformat(),
                "score": r.score,
                "warnings": list(r.warnings),
            }
            for r in results
        ],
        "errors": errors if errors else None,
    }
