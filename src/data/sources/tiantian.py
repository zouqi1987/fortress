"""天天基金 data source adapter — backup source for Chinese fund data.

Delegates to shared eastmoney API helpers. 2 retries, 1s interval.
Tiantian differs from EastmoneySource by having a shorter retry strategy
and not supporting index daily data.
"""
import logging
import time
from datetime import date

from src.data.sources._eastmoney_base import fetch_fund_info, fetch_fund_nav
from src.datatypes import FundInfo, IndexPoint, NAVPoint

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

    # ── Implementation (delegates to shared eastmoney base) ───────────

    def _fetch_fund_nav_impl(self, code: str, start: date, end: date) -> list[NAVPoint]:
        return fetch_fund_nav(code, start, end)

    def _fetch_fund_info_impl(self, code: str) -> FundInfo:
        return fetch_fund_info(code)

    def _fetch_index_daily_impl(self, code: str, start: date, end: date) -> list[IndexPoint]:
        raise NotImplementedError("TiantianSource does not support index daily data")
