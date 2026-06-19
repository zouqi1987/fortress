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
                # Rate-limit BEFORE each attempt after the first
                if attempt > 1:
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
        """Fetch NAV via eastmoney direct API (more reliable than akshare wrapper)."""
        from src.data.sources._eastmoney_base import fetch_fund_nav
        return fetch_fund_nav(code, start, end)

    def _fetch_fund_info_impl(self, code: str) -> FundInfo:
        """Fetch fund basic info via akshare xueqiu API (eastmoney API deprecated)."""
        import akshare as ak

        # Primary: xueqiu API (working as of 2026-06)
        try:
            df = ak.fund_individual_basic_info_xq(symbol=code)
            if df is not None and not df.empty:
                info: dict[str, str] = {}
                for _, row in df.iterrows():
                    key = str(row.iloc[0]).strip()
                    val = str(row.iloc[1]).strip() if row.iloc[1] is not None else ""
                    info[key] = val

                name = info.get("基金名称", info.get("基金简称", code))
                fund_type_raw = info.get("基金类型", "mixed")

                # Parse size e.g. "26.44亿"
                size_str = info.get("最新规模", info.get("基金规模", "0"))
                nav_value = _parse_chinese_amount(size_str) if size_str != "--" else Decimal("0")

                inception_str = info.get("成立时间", info.get("成立日期", "2020-01-01"))
                inception = _parse_date(inception_str) if inception_str != "--" else date(2020, 1, 1)

                return FundInfo(
                    code=code,
                    name=name,
                    type=classify_fund_type(fund_type_raw),
                    net_asset_value=nav_value,
                    fee_rate=Decimal("0.015"),  # xueqiu doesn't provide fee rate
                    inception_date=inception,
                )
        except Exception:
            pass

        # Fallback: old eastmoney API (may be deprecated)
        df = ak.fund_open_fund_info_em(symbol=code, indicator="基金信息")
        if df is None or df.empty:
            raise ValueError(f"No fund info returned for {code} (both xueqiu and eastmoney APIs failed)")

        info = {}
        for _, row in df.iterrows():
            info[str(row.iloc[0]).strip()] = str(row.iloc[1]).strip() if row.iloc[1] is not None else ""

        return FundInfo(
            code=code,
            name=info.get("基金简称", code),
            type=classify_fund_type(info.get("基金类型", "mixed")),
            net_asset_value=_parse_chinese_amount(info.get("基金规模", "0")),
            fee_rate=Decimal("0.015"),
            inception_date=_parse_date(info.get("成立日期", "2020-01-01")),
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
    """Parse date from various Chinese date formats. Raises on failure."""
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
        raise ValueError(f"Cannot parse date: {raw!r}")


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
