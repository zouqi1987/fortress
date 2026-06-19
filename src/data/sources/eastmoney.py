"""东方财富 data source adapter — backup for index/market data.

Uses eastmoney push2 API for index daily data.
"""
import json
import logging
import time
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.datatypes import FundInfo, IndexPoint, NAVPoint

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 2  # seconds


class EastmoneySource:
    """Backup source — eastmoney push2 API for index data."""

    name = "eastmoney"

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
                return fn(*args)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "eastmoney %s attempt %d/%d failed: %s",
                        fn.__name__, attempt, MAX_RETRIES, e,
                    )
                    time.sleep(RETRY_DELAY)
        raise last_error  # type: ignore[misc]

    # ── Implementation ───────────────────────────────────────────────

    def _fetch_fund_nav_impl(self, code: str, start: date, end: date) -> list[NAVPoint]:
        """Delegate to eastmoney fund NAV API."""
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
                raise ConnectionError(f"eastmoney NAV request failed: {e}") from e

            json_str = raw[raw.index("(") + 1 : raw.rindex(")")]
            data = json.loads(json_str)

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

        return points

    def _fetch_fund_info_impl(self, code: str) -> FundInfo:
        """Delegate to eastmoney fund info API."""
        # Reuse the same eastmoney API as tiantian
        from src.data.sources.tiantian import TiantianSource

        tiantian = TiantianSource()
        return tiantian.fetch_fund_info(code)

    def _fetch_index_daily_impl(self, code: str, start: date, end: date) -> list[IndexPoint]:
        """Fetch index daily via eastmoney push2 API."""
        import urllib.request

        # Build eastmoney market code (1=SH, 0=SZ)
        if code.startswith("6"):
            secid = f"1.{code}"
        elif code.startswith("0") or code.startswith("3"):
            secid = f"0.{code}"
        elif code.startswith("000"):
            secid = f"1.{code}"  # SH index
        elif code.startswith("399"):
            secid = f"0.{code}"  # SZ index
        else:
            secid = f"1.{code}"

        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
            f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt=101&fqt=1&beg={start.strftime('%Y%m%d')}&end={end.strftime('%Y%m%d')}"
        )
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as e:
            raise ConnectionError(f"eastmoney index request failed: {e}") from e

        data = json.loads(raw)
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            raise ValueError(f"No index data returned for {code}")

        points: list[IndexPoint] = []
        for line in klines:
            parts = line.split(",")
            try:
                d = date.fromisoformat(parts[0][:10]) if "-" in parts[0] else date.strptime(parts[0], "%Y-%m-%d")  # type: ignore[return-value]
                close = Decimal(parts[2]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                volume = Decimal(parts[5]).quantize(Decimal("0"), rounding=ROUND_HALF_UP)
                points.append(IndexPoint(date=d, close=close, volume=volume))
            except (ValueError, IndexError):
                continue

        return points
