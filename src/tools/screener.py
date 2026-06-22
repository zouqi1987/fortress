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
    benchmark_data: dict | None = None,
    risk_level: str = "",
) -> dict:
    """Screen and rank a list of funds. v1 static scoring default; v2 when nav_data provided.

    Args:
        funds: List of fund dicts, each with:
            code, name, type, net_asset_value, fee_rate, inception_date ("YYYY-MM-DD").
        min_net_asset_value: Minimum fund size filter (CNY). 0 = no filter.
        allowed_types: Comma-separated fund types, e.g. "bond,mixed". Empty = all.
        max_fee_rate: Maximum acceptable fee rate (e.g. 0.015 = 1.5%).
        nav_data: Optional {code: [nav_values]} for v2 5-dimension scoring.
        benchmark_data: Optional {fund_type: [benchmark_navs]} for relative scoring.
        risk_level: Optional "conservative"|"moderate"|"aggressive" to personalize scores.
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
    results = _screen(fund_infos, config, nav_data, benchmark_data=benchmark_data)

    # ── Risk-level personalization ────────────────────────────────────
    if risk_level and nav_data:
        results = _apply_risk_personalization(results, nav_data, risk_level)

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
        "personalized": risk_level if risk_level else False,
    }


def _apply_risk_personalization(
    results: list,
    nav_data: dict,
    risk_level: str,
) -> list:
    """Apply risk-level adjustments to screening scores.

    conservative: penalize volatile funds (>15% ann_vol → -10, >8% → -5),
                  reward very stable ones (<3% → +3).
    aggressive: reward high return funds (>10% 1y → +5),
                penalize too-safe (<1% 1y → -3).
    moderate: no adjustment.

    ScreenResult is frozen, so we rebuild results with adjusted scores.
    """
    if not results or risk_level == "moderate" or risk_level not in ("conservative", "aggressive"):
        return results

    from src.engine.screener import ScreenResult

    # Compute metrics per fund
    adj: dict[str, int] = {}
    for r in results:
        nv = nav_data.get(r.fund.code, [])
        if len(nv) < 63:
            continue
        prices = [float(v) for v in nv]
        ret_1y = (prices[-1] / prices[0] - 1) if prices[0] > 0 else 0.0
        daily_returns = [
            prices[i] / prices[i - 1] - 1
            for i in range(1, len(prices))
            if prices[i - 1] > 0
        ]
        if len(daily_returns) < 10:
            continue
        mean_r = sum(daily_returns) / len(daily_returns)
        variance = sum((x - mean_r) ** 2 for x in daily_returns) / len(daily_returns)
        ann_vol = variance ** 0.5 * (252 ** 0.5)

        delta = 0
        if risk_level == "conservative":
            if ann_vol > 0.15:
                delta = -10
            elif ann_vol > 0.08:
                delta = -5
            elif ann_vol < 0.03:
                delta = 3
        elif risk_level == "aggressive":
            if ret_1y > 0.10:
                delta = 5
            elif ret_1y < 0.01 and ret_1y >= 0:
                delta = -3

        if delta != 0:
            adj[r.fund.code] = delta

    if not adj:
        return results

    adjusted = [
        ScreenResult(
            fund=r.fund,
            score=max(0, min(100, r.score + adj.get(r.fund.code, 0))),
            warnings=r.warnings,
        )
        for r in results
    ]
    adjusted.sort(key=lambda r: r.score, reverse=True)
    return adjusted
