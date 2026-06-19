"""AKShare data source adapter — primary source for Chinese fund/ETF data.

3 retries with exponential backoff (1s/2s/4s). 2s interval between calls.
Converts akshare DataFrames to fortress DTOs.
"""
import logging
import time
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.datatypes import FundInfo, IndexPoint, NAVPoint, classify_fund_type

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds: 1, 2, 4


class AKShareSource:
    """Primary data source via akshare library."""

    name = "akshare"

    def fetch_fund_nav(self, code: str, start: date, end: date) -> list[NAVPoint]:
        """Fetch fund NAV history from akshare."""
        return self._retry(self._fetch_fund_nav_impl, code, start, end)

    def fetch_fund_info(self, code: str) -> FundInfo:
        """Fetch fund basic info from akshare."""
        return self._retry(self._fetch_fund_info_impl, code)

    def fetch_index_daily(self, code: str, start: date, end: date) -> list[IndexPoint]:
        """Fetch index daily data from akshare."""
        return self._retry(self._fetch_index_daily_impl, code, start, end)

    # ── Retry logic ─────────────────────────────────────────────────

    def _retry(self, fn, *args):
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Rate-limit: 2s between akshare calls
                time.sleep(2)
                return fn(*args)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "akshare %s attempt %d/%d failed: %s. Retrying in %ds...",
                        fn.__name__, attempt, MAX_RETRIES, e, wait,
                    )
                    time.sleep(wait)
        raise last_error  # type: ignore[misc]

    # ── Implementation ──────────────────────────────────────────────

    def _fetch_fund_nav_impl(self, code: str, start: date, end: date) -> list[NAVPoint]:
        import akshare as ak

        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            raise ValueError(f"No NAV data returned for fund {code}")

        points: list[NAVPoint] = []
        for _, row in df.iterrows():
            d = _parse_date(row.iloc[0])
            if d < start or d > end:
                continue
            try:
                nav = Decimal(str(row.iloc[1])).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                acc_nav = Decimal(str(row.iloc[2])).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            except (ValueError, IndexError):
                continue
            points.append(NAVPoint(date=d, nav=nav, acc_nav=acc_nav))
        return points

    def _fetch_fund_info_impl(self, code: str) -> FundInfo:
        import akshare as ak

        df = ak.fund_open_fund_info_em(symbol=code, indicator="基金信息")
        if df is None or df.empty:
            raise ValueError(f"No fund info returned for {code}")

        # akshare returns a DataFrame with columns: 项目, 内容
        info: dict[str, str] = {}
        for _, row in df.iterrows():
            info[str(row.iloc[0]).strip()] = str(row.iloc[1]).strip() if row.iloc[1] is not None else ""

        fee_rate = Decimal("0.015")  # default
        nav_str = info.get("基金规模", "0")
        # Parse "12.34亿元" format
        nav_value = _parse_chinese_amount(nav_str)

        inception = _parse_date(info.get("成立日期", "2020-01-01"))

        return FundInfo(
            code=code,
            name=info.get("基金简称", code),
            type=classify_fund_type(info.get("基金类型", "mixed")),
            net_asset_value=nav_value,
            fee_rate=fee_rate,
            inception_date=inception,
        )

    def _fetch_index_daily_impl(self, code: str, start: date, end: date) -> list[IndexPoint]:
        import akshare as ak

        df = ak.index_zh_a_hist(symbol=code, period="daily", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
        if df is None or df.empty:
            raise ValueError(f"No index data returned for {code}")

        points: list[IndexPoint] = []
        for _, row in df.iterrows():
            try:
                d = _parse_date(str(row["日期"]))
                close = Decimal(str(row["收盘"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                volume = Decimal(str(row["成交量"] or 0)).quantize(Decimal("0"), rounding=ROUND_HALF_UP)
                points.append(IndexPoint(date=d, close=close, volume=volume))
            except (ValueError, KeyError):
                continue
        return points


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_date(raw: str) -> date:
    """Parse date from various Chinese date formats."""
    raw = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return date.fromisoformat(raw) if fmt == "%Y-%m-%d" else date.strptime(raw, fmt)  # type: ignore[return-value]
        except (ValueError, TypeError):
            continue
    # Try just YYYY-MM-DD prefix
    try:
        return date.fromisoformat(raw[:10])
    except (ValueError, TypeError):
        return date(2000, 1, 1)


def _parse_chinese_amount(raw: str) -> Decimal:
    """Parse amount like '12.34亿元' or '5000万元' to Decimal."""
    raw = raw.strip()
    if not raw or raw == "--":
        return Decimal("0")
    try:
        return Decimal(raw)
    except Exception:
        pass
    # Extract numeric part
    num_str = ""
    unit_mult: Decimal = Decimal("1")
    for i, ch in enumerate(raw):
        if ch.isdigit() or ch in (".", "-"):
            num_str += ch
        elif ch == "亿":
            unit_mult = Decimal("100_000_000")
            break
        elif ch == "万":
            unit_mult = Decimal("10_000")
            break
    try:
        return Decimal(num_str) * unit_mult if num_str else Decimal("0")
    except Exception:
        return Decimal("0")


# classify_fund_type now imported from src.datatypes
