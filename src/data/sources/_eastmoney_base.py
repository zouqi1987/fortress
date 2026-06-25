"""Shared eastmoney API helpers — used by TiantianSource and EastmoneySource.

Both sources query the same eastmoney API endpoints; this module eliminates
the ~120-line duplication between them. Each source retains its own retry
strategy and identity.
"""
import json
import logging
import urllib.request
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.datatypes import FundInfo, NAVPoint, classify_fund_type

logger = logging.getLogger(__name__)

# Pagination guard: max pages to fetch (prevents infinite loop)
MAX_PAGES = 50


def parse_jsonp(raw: str) -> dict:
    """Parse JSONP response robustly. Handles missing/malformed callbacks."""
    raw = raw.strip()
    if "(" in raw and raw.rstrip().endswith(")"):
        json_str = raw[raw.index("(") + 1 : raw.rindex(")")]
        return json.loads(json_str)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Unrecognized response format (first 200 chars): {raw[:200]}")


def fetch_fund_nav(code: str, start: date, end: date) -> list[NAVPoint]:
    """Fetch NAV via eastmoney fund API (shared by all eastmoney-based sources)."""
    page_index = 1
    page_size = 20  # eastmoney API caps at 20 per page regardless of parameter
    points: list[NAVPoint] = []

    while page_index <= MAX_PAGES:
        url = (
            f"https://api.fund.eastmoney.com/f10/lsjz?"
            f"callback=jQuery&fundCode={code}&pageIndex={page_index}&pageSize={page_size}"
            f"&startDate={start.strftime('%Y-%m-%d')}&endDate={end.strftime('%Y-%m-%d')}"
        )
        req = urllib.request.Request(url)
        req.add_header("Referer", "https://fundf10.eastmoney.com/")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as e:
            raise ConnectionError(f"eastmoney NAV request failed: {e}") from e

        data = parse_jsonp(raw)
        if data.get("ErrCode") != 0:
            raise ValueError(f"eastmoney API error: {data.get('ErrMsg', 'unknown')}")

        items = data.get("Data", {}).get("LSJZList", [])
        if not items:
            break

        for item in items:
            try:
                d = date.fromisoformat(item["FSRQ"])
                nav = Decimal(str(item["DWJZ"])).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                acc_nav = Decimal(str(item.get("LJJZ", item["DWJZ"]))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                points.append(NAVPoint(date=d, nav=nav, acc_nav=acc_nav))
            except (KeyError, ValueError):
                continue

        if len(items) < page_size:
            break
        page_index += 1
    else:
        logger.warning("fetch_fund_nav: reached MAX_PAGES=%d for fund %s", MAX_PAGES, code)

    points.sort(key=lambda p: p.date)  # chronological order (oldest first)
    return points


def fetch_fund_info(code: str) -> FundInfo:
    """Fetch fund basic info via eastmoney API (shared by all eastmoney-based sources)."""
    url = f"https://api.fund.eastmoney.com/f10/fundInfo?callback=jQuery&fundCode={code}"
    req = urllib.request.Request(url)
    req.add_header("Referer", "https://fundf10.eastmoney.com/")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        raise ConnectionError(f"eastmoney info request failed: {e}") from e

    data = parse_jsonp(raw)
    if data.get("ErrCode") != 0:
        raise ValueError(f"eastmoney fund info error: {data.get('ErrMsg', 'unknown')}")

    info = data.get("Data", {})
    nav_str = info.get("AssetSize", "0")
    try:
        nav_value = Decimal(str(nav_str)) if nav_str else Decimal("0")
    except Exception:
        nav_value = Decimal("0")

    fee_str = info.get("Rate", "0.015")
    try:
        fee_rate = Decimal(str(fee_str)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except Exception:
        fee_rate = Decimal("0.015")

    inception_str = info.get("FoundDate", "2020-01-01")
    try:
        inception = date.fromisoformat(str(inception_str)[:10])
    except (ValueError, TypeError):
        inception = date(2020, 1, 1)

    return FundInfo(
        code=code,
        name=info.get("FundName", code),
        type=classify_fund_type(info.get("FundType", "mixed")),
        net_asset_value=nav_value,
        fee_rate=fee_rate,
        inception_date=inception,
    )
