"""NAV time-series storage — SQLite-backed fund NAV history.

Task 2a: schema + read/query methods. Pure DB operations.
Task 2b: backfill (concurrent, idempotent, resumable).

Schema:
  fund_nav(code, nav_date, unit_nav, accum_nav) — PK(code, nav_date)
  nav_backfill_progress(code, status, fetched_at, point_count) — for resumable backfill

Historical NAV points are immutable once stored (INSERT OR IGNORE).
"""
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class BackfillReport:
    """Report from a backfill run. Follows StressResult pattern (frozen dataclass).

    Attributes:
        fetched: Codes newly fetched this run.
        skipped: Codes already "done" (resumable skip).
        failed: Codes that errored during fetch.
        point_count: Total NAV rows inserted.
        failed_codes: Which codes failed (for re-run targeting).
    """

    fetched: int
    skipped: int
    failed: int
    point_count: int
    failed_codes: list[str]


@dataclass(frozen=True)
class UpdateReport:
    """Report from an update run — gap detection + tiered recovery.

    Attributes:
        latest_db_date: Most recent nav_date in the store (None if empty).
        latest_trading_date: Most recent trading date from the calendar.
        gap_days: Number of trading days the store is behind.
        action: What was done — "current" | "bulk_update" | "recovery_mode"
                | "manual_backfill_needed".
        funds_updated: Number of funds that got new data this update.
        points_added: Total NAV rows inserted this update.
    """

    latest_db_date: str | None
    latest_trading_date: str
    gap_days: int
    action: str
    funds_updated: int
    points_added: int


class NavStore:
    """SQLite-backed store for fund NAV time-series data.

    Args:
        db_path: Path to SQLite database file. Parent dirs auto-created.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._recovery_needed = False
        self._trading_dates: list[str] | None = None
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fund_nav (
                code        TEXT NOT NULL,
                nav_date    TEXT NOT NULL,
                unit_nav    REAL NOT NULL,
                accum_nav   REAL,
                PRIMARY KEY (code, nav_date)
            );
            CREATE INDEX IF NOT EXISTS idx_fund_nav_code ON fund_nav(code);
            CREATE INDEX IF NOT EXISTS idx_fund_nav_date ON fund_nav(nav_date);

            CREATE TABLE IF NOT EXISTS nav_backfill_progress (
                code        TEXT PRIMARY KEY,
                status      TEXT NOT NULL,
                fetched_at  TEXT,
                point_count INTEGER
            );
            """
        )
        self._conn.commit()

    def append_nav(
        self, code: str, nav_date: str, unit_nav: float, accum_nav: float | None = None
    ) -> None:
        """Insert a NAV point. Idempotent — INSERT OR IGNORE (historical immutable).

        Args:
            code: Fund code (e.g. "217022").
            nav_date: ISO date string "YYYY-MM-DD".
            unit_nav: Unit net asset value (单位净值).
            accum_nav: Cumulative net asset value (累计净值), nullable.
        """
        self._conn.execute(
            "INSERT OR IGNORE INTO fund_nav (code, nav_date, unit_nav, accum_nav) "
            "VALUES (?, ?, ?, ?)",
            (code, nav_date, unit_nav, accum_nav),
        )
        self._conn.commit()

    def get_nav_series(self, code: str, days: int = 750) -> list[float]:
        """Return daily unit_nav for a fund, oldest-first.

        If ``_recovery_needed`` is True and the code has no data in the store,
        triggers a lazy per-fund fetch (``_fetch_one`` with period='1月')
        before returning. This ensures queried funds get recovered on-demand
        without blocking on a full bulk update.

        Args:
            code: Fund code.
            days: Max number of most-recent points to return (default 750 ≈ 3 years).

        Returns:
            List of unit_nav values, oldest-first. Empty if code not found.
        """
        rows = self._conn.execute(
            "SELECT unit_nav FROM fund_nav WHERE code = ? "
            "ORDER BY nav_date DESC LIMIT ?",
            (code, days),
        ).fetchall()

        if not rows and self._recovery_needed:
            # Lazy recovery: fetch this fund's recent NAV on-demand
            try:
                nav_points = self._fetch_one(code, "1月")
                self._conn.executemany(
                    "INSERT OR IGNORE INTO fund_nav "
                    "(code, nav_date, unit_nav, accum_nav) VALUES (?, ?, ?, ?)",
                    [(code, d, v, None) for d, v in nav_points],
                )
                self._conn.commit()
                rows = self._conn.execute(
                    "SELECT unit_nav FROM fund_nav WHERE code = ? "
                    "ORDER BY nav_date DESC LIMIT ?",
                    (code, days),
                ).fetchall()
            except Exception:
                pass  # Lazy recovery failed — return empty, don't crash

        return [r[0] for r in reversed(rows)]

    def get_latest_date(self) -> str | None:
        """Return the most recent nav_date in the store, or None if empty."""
        row = self._conn.execute(
            "SELECT MAX(nav_date) FROM fund_nav"
        ).fetchone()
        return row[0] if row else None

    def coverage_report(self, pool_codes: list[str] | None = None) -> dict:
        """Report NAV coverage.

        Args:
            pool_codes: If provided, computes with_nav / missing_nav / coverage_rate
                        against this list. If None, returns DB-only stats.

        Returns:
            Always: fund_count (distinct codes in store), latest_date, total_points.
            If pool_codes provided: also total_pool, with_nav, missing_nav, coverage_rate.
        """
        fund_count_row = self._conn.execute(
            "SELECT COUNT(DISTINCT code) FROM fund_nav"
        ).fetchone()
        total_points_row = self._conn.execute(
            "SELECT COUNT(*) FROM fund_nav"
        ).fetchone()

        report: dict = {
            "fund_count": fund_count_row[0],
            "latest_date": self.get_latest_date(),
            "total_points": total_points_row[0],
        }

        if pool_codes is not None:
            if not pool_codes:
                report["total_pool"] = 0
                report["with_nav"] = 0
                report["missing_nav"] = 0
                report["coverage_rate"] = 0.0
            else:
                with_nav = self._conn.execute(
                    "SELECT COUNT(DISTINCT code) FROM fund_nav WHERE code IN (%s)"
                    % ",".join("?" * len(pool_codes)),
                    pool_codes,
                ).fetchone()[0]
                report["total_pool"] = len(pool_codes)
                report["with_nav"] = with_nav
                report["missing_nav"] = len(pool_codes) - with_nav
                report["coverage_rate"] = with_nav / len(pool_codes)

        return report

    def stats(self) -> dict:
        """Return store summary: fund count, date range, total points."""
        fund_count_row = self._conn.execute(
            "SELECT COUNT(DISTINCT code) FROM fund_nav"
        ).fetchone()
        total_points_row = self._conn.execute(
            "SELECT COUNT(*) FROM fund_nav"
        ).fetchone()
        date_range_row = self._conn.execute(
            "SELECT MIN(nav_date), MAX(nav_date) FROM fund_nav"
        ).fetchone()

        return {
            "fund_count": fund_count_row[0],
            "date_range": tuple(date_range_row) if date_range_row[0] else None,
            "total_points": total_points_row[0],
        }

    # ── Backfill (Task 2b) ────────────────────────────────────────────

    def backfill(
        self,
        codes: list[str],
        period: str = "3年",
        max_workers: int = 5,
    ) -> BackfillReport:
        """Concurrent, idempotent, resumable NAV backfill.

        Workers do HTTP only (``_fetch_one`` is a staticmethod with no DB
        access). The main thread does all DB inserts + progress updates —
        no SQLite thread-safety issues.

        Args:
            codes: Fund codes to backfill.
            period: Lookback period (e.g. "3年", "1年", "成立来").
            max_workers: Max concurrent HTTP fetches (default 5, per
                         architecture rule ``02-architecture.md``: 并发 ≤5).

        Returns:
            BackfillReport with fetched/skipped/failed counts.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not codes:
            return BackfillReport(0, 0, 0, 0, [])

        # 1. Init progress for all codes (idempotent — skip existing)
        for code in codes:
            self._conn.execute(
                "INSERT OR IGNORE INTO nav_backfill_progress (code, status) "
                "VALUES (?, 'pending')",
                (code,),
            )
        self._conn.commit()

        # 2. Filter: skip codes already "done"
        to_fetch = [c for c in codes if self._get_progress(c) != "done"]
        skipped = len(codes) - len(to_fetch)

        # 3. Concurrent fetch (workers = HTTP only)
        fetched = failed = total_points = 0
        failed_codes: list[str] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._fetch_one, code, period): code
                for code in to_fetch
            }
            for future in as_completed(future_map):
                code = future_map[future]
                try:
                    nav_points = future.result()
                    # Main thread: bulk insert
                    self._conn.executemany(
                        "INSERT OR IGNORE INTO fund_nav "
                        "(code, nav_date, unit_nav, accum_nav) VALUES (?, ?, ?, ?)",
                        [(code, d, v, None) for d, v in nav_points],
                    )
                    self._conn.execute(
                        "UPDATE nav_backfill_progress SET status='done', "
                        "fetched_at=?, point_count=? WHERE code=?",
                        (datetime.now().isoformat(), len(nav_points), code),
                    )
                    self._conn.commit()
                    fetched += 1
                    total_points += len(nav_points)
                except Exception:
                    self._conn.execute(
                        "UPDATE nav_backfill_progress SET status='failed' "
                        "WHERE code=?",
                        (code,),
                    )
                    self._conn.commit()
                    failed += 1
                    failed_codes.append(code)

        return BackfillReport(fetched, skipped, failed, total_points, failed_codes)

    @staticmethod
    def _fetch_one(code: str, period: str) -> list[tuple[str, float]]:
        """Fetch NAV for one fund. HTTP only — no self/DB access (thread-safe).

        Returns list of (nav_date_str, unit_nav_float), oldest-first.
        Raises RuntimeError if API returns empty/None.
        """
        import akshare as ak

        df = ak.fund_open_fund_info_em(
            symbol=code, indicator="单位净值走势", period=period
        )
        if df is None or df.empty:
            raise RuntimeError(f"Empty NAV data for {code}")
        return [
            (str(d), float(v))
            for d, v in zip(df["净值日期"], df["单位净值"])
        ]

    def _get_progress(self, code: str) -> str | None:
        """Return backfill status for a code, or None if not tracked."""
        row = self._conn.execute(
            "SELECT status FROM nav_backfill_progress WHERE code=?", (code,)
        ).fetchone()
        return row[0] if row else None

    # ── Update (Task 2c) — gap detection + tiered recovery ────────────

    def update(self) -> UpdateReport:
        """Detect gap between store and latest trading date, take tiered action.

        - gap ≤ 0: store is current (action="current")
        - gap ≤ 2 trading days: bulk append via ``fund_open_fund_daily_em``
          (action="bulk_update")
        - gap 3-30: set ``_recovery_needed`` for lazy per-fund recovery
          (action="recovery_mode")
        - gap > 30: defer to manual ``backfill()`` (action="manual_backfill_needed")

        Returns:
            UpdateReport with gap info + action taken.
        """
        latest_db_date = self.get_latest_date()
        trading_dates = self._get_trading_dates()
        # Filter to past dates only — tool_trade_date_hist_sina returns full-year
        # calendar including future dates up to Dec 31
        today_str = date.today().isoformat()
        past_trading_dates = [d for d in trading_dates if d <= today_str]
        latest_trading_date = past_trading_dates[-1] if past_trading_dates else ""

        if latest_db_date is None:
            return UpdateReport(
                latest_db_date=None,
                latest_trading_date=latest_trading_date,
                gap_days=999,
                action="manual_backfill_needed",
                funds_updated=0,
                points_added=0,
            )

        # Count trading dates after latest_db_date (past dates only)
        gap_dates = [d for d in past_trading_dates if d > latest_db_date]
        gap_days = len(gap_dates)

        if gap_days <= 0:
            return UpdateReport(
                latest_db_date=latest_db_date,
                latest_trading_date=latest_trading_date,
                gap_days=0,
                action="current",
                funds_updated=0,
                points_added=0,
            )

        if gap_days <= 2:
            # Bulk update: fetch latest NAV for ALL funds in 1 HTTP call
            daily_rows = self._fetch_daily_em()
            funds_updated = len({r[0] for r in daily_rows})
            self._conn.executemany(
                "INSERT OR IGNORE INTO fund_nav "
                "(code, nav_date, unit_nav, accum_nav) VALUES (?, ?, ?, ?)",
                [(c, d, v, None) for c, d, v in daily_rows],
            )
            self._conn.commit()
            return UpdateReport(
                latest_db_date=latest_db_date,
                latest_trading_date=latest_trading_date,
                gap_days=gap_days,
                action="bulk_update",
                funds_updated=funds_updated,
                points_added=len(daily_rows),
            )

        if gap_days <= 30:
            # Recovery mode: lazy-recover queried funds on-demand
            self._recovery_needed = True
            return UpdateReport(
                latest_db_date=latest_db_date,
                latest_trading_date=latest_trading_date,
                gap_days=gap_days,
                action="recovery_mode",
                funds_updated=0,
                points_added=0,
            )

        # gap > 30: defer to manual backfill
        return UpdateReport(
            latest_db_date=latest_db_date,
            latest_trading_date=latest_trading_date,
            gap_days=gap_days,
            action="manual_backfill_needed",
            funds_updated=0,
            points_added=0,
        )

    def _get_trading_dates(self) -> list[str]:
        """Fetch and cache the trading date calendar from akshare.

        Returns list of ISO date strings (YYYY-MM-DD). Cached on first call.
        """
        if self._trading_dates is not None:
            return self._trading_dates
        import akshare as ak

        df = ak.tool_trade_date_hist_sina()
        # Column 'trade_date' contains date objects — convert to ISO strings
        self._trading_dates = [str(d) for d in df["trade_date"].tolist()]
        return self._trading_dates

    @staticmethod
    def _fetch_daily_em() -> list[tuple[str, str, float]]:
        """Fetch latest NAV for ALL funds via bulk endpoint (1 HTTP call).

        Returns list of (code, nav_date_str, unit_nav_float).
        Parses columns like '2026-06-24-单位净值' from fund_open_fund_daily_em.
        """
        import akshare as ak

        df = ak.fund_open_fund_daily_em()
        rows: list[tuple[str, str, float]] = []
        for col in df.columns:
            if col.endswith("-单位净值"):
                date_str = col.replace("-单位净值", "")
                for code, nav in zip(df["基金代码"], df[col]):
                    if nav is not None and str(nav) not in ("nan", "", "None"):
                        rows.append((str(code).zfill(6), date_str, float(nav)))
        return rows

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "NavStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[untyped-def]
        self.close()
        return False

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# ── CLI entry point ──────────────────────────────────────────────────


def _main():
    """Command-line interface for NavStore operations.

    Usage:
      python3 -m src.data.sources.nav_store --backfill          # full market backfill
      python3 -m src.data.sources.nav_store --backfill --period 1年  # shorter period
      python3 -m src.data.sources.nav_store --update             # daily incremental
      python3 -m src.data.sources.nav_store --stats              # inspect store
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="NavStore — fund NAV time-series storage management",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backfill", action="store_true",
                       help="Backfill NAV history for all pool funds")
    group.add_argument("--update", action="store_true",
                       help="Daily incremental update (gap detection + recovery)")
    group.add_argument("--stats", action="store_true",
                       help="Print store statistics")
    parser.add_argument("--period", default="3年",
                        help="Backfill lookback period (default: 3年)")
    parser.add_argument("--max-workers", type=int, default=5,
                        help="Max concurrent HTTP workers (default: 5, per architecture rule)")
    parser.add_argument("--db", default="data/market_cache.db",
                        help="SQLite database path (default: data/market_cache.db)")
    args = parser.parse_args()

    store = NavStore(args.db)

    if args.stats:
        stats = store.stats()
        coverage = store.coverage_report()
        print(f"Fund count:     {stats['fund_count']}")
        print(f"Total points:   {stats['total_points']}")
        print(f"Date range:     {stats['date_range']}")
        print(f"Latest date:    {coverage['latest_date']}")
        return

    if args.update:
        report = store.update()
        print(f"Action:         {report.action}")
        print(f"Gap days:       {report.gap_days}")
        print(f"Latest DB date: {report.latest_db_date}")
        print(f"Latest trading: {report.latest_trading_date}")
        print(f"Funds updated:  {report.funds_updated}")
        print(f"Points added:   {report.points_added}")
        return

    if args.backfill:
        # Fetch fund pool to get all codes
        print("Fetching fund pool...", flush=True)
        from src.data.sources.fund_pool import fetch_fund_pool
        pool = fetch_fund_pool()
        codes = [f.code for f in pool]
        print(f"Backfilling {len(codes)} funds (period={args.period}, "
              f"workers={args.max_workers})...", flush=True)

        report = store.backfill(codes, period=args.period, max_workers=args.max_workers)
        print(f"\nBackfill complete:")
        print(f"  Fetched:     {report.fetched}")
        print(f"  Skipped:     {report.skipped}")
        print(f"  Failed:      {report.failed}")
        print(f"  Points:      {report.point_count}")
        if report.failed_codes:
            print(f"  Failed codes (first 20): {report.failed_codes[:20]}")

        # Print final stats
        stats = store.stats()
        print(f"\nStore stats:")
        print(f"  Fund count:   {stats['fund_count']}")
        print(f"  Total points: {stats['total_points']}")
        print(f"  Date range:   {stats['date_range']}")
        return


if __name__ == "__main__":
    _main()
