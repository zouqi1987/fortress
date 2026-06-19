"""天天基金 data source adapter — backup source for Chinese fund data.

Direct HTTP queries to eastmoney fund API. 2 retries, 1s interval.
"""
import json
import logging
import time
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.data.market import FundInfo, IndexPoint, NAVPoint

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 1  # seconds


class TiantianSource:
    """Backup data source — queries eastmoney fund API directly."""

    name = "tiantian"

    def fetch_fund_nav(self, code: str, start: date, end: date) -> list[NAVPoint]:
        return self._retry(self._fetch_fund_nav_impl, code, start, end)

    def fetch_fund_info(self, code: str) -> FundInfo:
        return self._retry(self._fetch_fund_info_impl, code)

    def fetch_index_daily(self, code: str, start: date, end: date) -> list[IndexPoint]:
        return self._retry(self._fetch_index_daily_impl, code, start, end)

    # ── Retry ────────────────────────────────────────────────────────

    def _retry(self, fn, *args):
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                time.sleep(1)
                return fn(*args)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "tiantian %s attempt %d/%d failed: %s",
                        fn.__name__, attempt, MAX_RETRIES, e,
                    )
                    time.sleep(RETRY_DELAY)
        raise last_error  # type: ignore[misc]

    # ── Implementation ───────────────────────────────────────────────

    def _fetch_fund_nav_impl(self, code: str, start: date, end: date) -> list[NAVPoint]:
        """Fetch NAV via eastmoney fund API."""
        import urllib.request

        page_index = 1
        page_size = 100
        points: list[NAVPoint] = []

        while True:
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
                raise ConnectionError(f"tiantian NAV request failed: {e}") from e

            # Parse JSONP: jQuery(...)
            json_str = raw[raw.index("(") + 1 : raw.rindex(")")]
            data = json.loads(json_str)

            if data.get("ErrCode") != 0:
                raise ValueError(f"tiantian API error: {data.get('ErrMsg', 'unknown')}")

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

        return points

    def _fetch_fund_info_impl(self, code: str) -> FundInfo:
        """Fetch fund basic info via eastmoney API."""
        import urllib.request

        url = (
            f"https://api.fund.eastmoney.com/f10/fundInfo?"
            f"callback=jQuery&fundCode={code}"
        )
        req = urllib.request.Request(url)
        req.add_header("Referer", "https://fundf10.eastmoney.com/")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as e:
            raise ConnectionError(f"tiantian info request failed: {e}") from e

        json_str = raw[raw.index("(") + 1 : raw.rindex(")")]
        data = json.loads(json_str)

        if data.get("ErrCode") != 0:
            raise ValueError(f"tiantian fund info error: {data.get('ErrMsg', 'unknown')}")

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
            type=_classify_fund_type(info.get("FundType", "mixed")),
            net_asset_value=nav_value,
            fee_rate=fee_rate,
            inception_date=inception,
        )

    def _fetch_index_daily_impl(self, code: str, start: date, end: date) -> list[IndexPoint]:
        """Not supported for tiantian — indexes are fetched via akshare or eastmoney."""
        raise NotImplementedError("TiantianSource does not support index daily data")


def _classify_fund_type(raw: str) -> str:
    raw_lower = str(raw).lower().strip()
    if any(k in raw_lower for k in ("股票", "stock")):
        return "stock"
    if any(k in raw_lower for k in ("指数", "index")):
        return "index"
    if any(k in raw_lower for k in ("债券", "bond")):
        return "bond"
    if any(k in raw_lower for k in ("货币", "money")):
        return "money"
    if any(k in raw_lower for k in ("混合", "mixed", "平衡")):
        return "mixed"
    return "mixed"
