"""Tests for NavStore — SQLite-backed NAV time-series storage.

Task 2a: schema creation + read/query methods. No akshare calls — pure DB.
Task 2b: backfill (concurrent, idempotent, resumable) — _fetch_one mocked.
Task 2c: update (gap detection + tiered recovery) — helpers mocked.
Uses tmp_path for isolated SQLite databases per test.
"""
import pytest
from unittest import mock

from src.data.sources.nav_store import NavStore, BackfillReport, UpdateReport


class TestSchemaCreation:
    def test_tables_created_on_init(self, tmp_path):
        """fund_nav + nav_backfill_progress tables exist after init."""
        store = NavStore(str(tmp_path / "nav.db"))
        rows = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {r[0] for r in rows}
        assert "fund_nav" in table_names
        assert "nav_backfill_progress" in table_names

    def test_init_idempotent(self, tmp_path):
        """Re-opening an existing DB doesn't crash or duplicate tables."""
        db_path = str(tmp_path / "nav.db")
        store1 = NavStore(db_path)
        store1.close()
        store2 = NavStore(db_path)  # should not raise
        tables = {r[0] for r in store2._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "fund_nav" in tables  # table still exists, no crash


class TestAppendNav:
    def test_append_and_get_nav_series(self, tmp_path):
        """Insert 3 NAV points → get_nav_series returns them oldest-first."""
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)
        store.append_nav("001", "2026-01-02", 1.01)
        store.append_nav("001", "2026-01-03", 1.02)

        series = store.get_nav_series("001")
        assert series == [1.0, 1.01, 1.02]

    def test_append_idempotent(self, tmp_path):
        """Same (code, date) twice → no duplicate, first value persists.

        Spec: historical NAV points are immutable once stored (INSERT OR IGNORE).
        """
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)
        store.append_nav("001", "2026-01-01", 1.05)  # ignored

        series = store.get_nav_series("001")
        assert len(series) == 1  # no duplicate
        assert series[0] == 1.0  # first value persists, not overwritten

    def test_append_accum_nav_optional(self, tmp_path):
        """accum_nav is optional (nullable)."""
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)  # no accum_nav

        row = store._conn.execute(
            "SELECT accum_nav FROM fund_nav WHERE code=?", ("001",)
        ).fetchone()
        assert row[0] is None


class TestGetNavSeries:
    def test_days_limit(self, tmp_path):
        """Request 2 days from 5 stored → returns last 2, oldest-first."""
        store = NavStore(str(tmp_path / "nav.db"))
        for i in range(5):
            store.append_nav("001", f"2026-01-0{i+1}", float(i + 1))

        series = store.get_nav_series("001", days=2)
        assert series == [4.0, 5.0]

    def test_missing_code_returns_empty(self, tmp_path):
        """Code not in DB → empty list, not error."""
        store = NavStore(str(tmp_path / "nav.db"))
        assert store.get_nav_series("999") == []

    def test_empty_store_returns_empty(self, tmp_path):
        """No data at all → empty list."""
        store = NavStore(str(tmp_path / "nav.db"))
        assert store.get_nav_series("001") == []

    def test_multiple_codes_isolated(self, tmp_path):
        """Fund A and B data don't leak into each other."""
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)
        store.append_nav("002", "2026-01-01", 2.0)

        assert store.get_nav_series("001") == [1.0]
        assert store.get_nav_series("002") == [2.0]


class TestGetLatestDate:
    def test_returns_most_recent(self, tmp_path):
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)
        store.append_nav("001", "2026-06-24", 1.5)
        store.append_nav("002", "2026-03-15", 2.0)

        assert store.get_latest_date() == "2026-06-24"

    def test_empty_store_returns_none(self, tmp_path):
        store = NavStore(str(tmp_path / "nav.db"))
        assert store.get_latest_date() is None


class TestCoverageReport:
    def test_empty_store(self, tmp_path):
        """Empty DB → fund_count 0, latest_date None."""
        store = NavStore(str(tmp_path / "nav.db"))
        report = store.coverage_report()
        assert report["fund_count"] == 0
        assert report["latest_date"] is None

    def test_with_pool_codes(self, tmp_path):
        """Pool codes provided → computes with_nav, missing_nav, coverage_rate."""
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)
        store.append_nav("002", "2026-01-01", 2.0)

        report = store.coverage_report(pool_codes=["001", "002", "003", "004"])
        assert report["total_pool"] == 4
        assert report["with_nav"] == 2
        assert report["missing_nav"] == 2
        assert report["coverage_rate"] == 0.5

    def test_without_pool_codes(self, tmp_path):
        """No pool_codes → returns fund_count only (no coverage_rate)."""
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)

        report = store.coverage_report()
        assert report["fund_count"] == 1
        assert "coverage_rate" not in report

    def test_empty_pool_codes_no_crash(self, tmp_path):
        """Empty pool_codes list → returns zeros, not SQL crash.

        Regression: ``WHERE code IN ()`` is invalid SQL. Must handle gracefully.
        """
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)

        report = store.coverage_report(pool_codes=[])
        assert report["total_pool"] == 0
        assert report["with_nav"] == 0
        assert report["missing_nav"] == 0
        assert report["coverage_rate"] == 0.0


class TestStats:
    def test_returns_summary(self, tmp_path):
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-01-01", 1.0)
        store.append_nav("001", "2026-06-24", 1.5)
        store.append_nav("002", "2026-03-15", 2.0)

        stats = store.stats()
        assert stats["fund_count"] == 2
        assert stats["date_range"] == ("2026-01-01", "2026-06-24")
        assert stats["total_points"] == 3

    def test_empty_store_stats(self, tmp_path):
        store = NavStore(str(tmp_path / "nav.db"))
        stats = store.stats()
        assert stats["fund_count"] == 0
        assert stats["date_range"] is None
        assert stats["total_points"] == 0


class TestBackfill:
    """Tests for NavStore.backfill() — concurrent, idempotent, resumable.

    _fetch_one is mocked (no live akshare calls). Tests verify:
    - data insertion + progress tracking
    - resumability (skip "done" codes)
    - failure isolation (failed codes don't crash batch)
    - idempotent re-run
    """

    @staticmethod
    def _fake_nav(code: str, n: int = 5) -> list[tuple[str, float]]:
        """Generate n fake (date, unit_nav) pairs for a code."""
        return [(f"2026-01-{i+1:02d}", 1.0 + i * 0.01) for i in range(n)]

    def test_backfill_fetches_and_stores(self, tmp_path):
        """3 codes, all succeed → fetched=3, data in fund_nav, progress='done'."""
        store = NavStore(str(tmp_path / "nav.db"))
        codes = ["001", "002", "003"]

        with mock.patch.object(NavStore, "_fetch_one", side_effect=[
            self._fake_nav("001"), self._fake_nav("002"), self._fake_nav("003"),
        ]):
            report = store.backfill(codes)

        assert report.fetched == 3
        assert report.failed == 0
        assert report.point_count == 15  # 3 codes × 5 points each
        # Data in fund_nav
        assert len(store.get_nav_series("001")) == 5
        assert len(store.get_nav_series("002")) == 5
        # Progress = done
        assert store._get_progress("001") == "done"
        assert store._get_progress("002") == "done"

    def test_backfill_skips_done_codes(self, tmp_path):
        """Pre-mark 1 code 'done' → skipped=1, only 2 fetched."""
        store = NavStore(str(tmp_path / "nav.db"))
        # Pre-insert done status for "001"
        store._conn.execute(
            "INSERT INTO nav_backfill_progress (code, status) VALUES (?, 'done')",
            ("001",)
        )
        store._conn.commit()

        with mock.patch.object(NavStore, "_fetch_one", side_effect=[
            self._fake_nav("002"), self._fake_nav("003"),
        ]):
            report = store.backfill(["001", "002", "003"])

        assert report.skipped == 1
        assert report.fetched == 2
        # "001" not fetched (no data in fund_nav)
        assert store.get_nav_series("001") == []

    def test_backfill_resumable_after_interrupt(self, tmp_path):
        """Codes marked 'pending' (interrupted) → backfill fetches them."""
        store = NavStore(str(tmp_path / "nav.db"))
        # Simulate interrupted: codes "pending" with no data
        store._conn.execute(
            "INSERT INTO nav_backfill_progress (code, status) VALUES (?, 'pending')",
            ("001",)
        )
        store._conn.commit()

        with mock.patch.object(NavStore, "_fetch_one", return_value=self._fake_nav("001")):
            report = store.backfill(["001"])

        assert report.fetched == 1
        assert report.skipped == 0
        assert len(store.get_nav_series("001")) == 5
        assert store._get_progress("001") == "done"

    def test_backfill_failed_code_marked(self, tmp_path):
        """1 code fails (exception) → status='failed', others still succeed."""
        store = NavStore(str(tmp_path / "nav.db"))

        def fetch_side_effect(code, period):
            if code == "002":
                raise RuntimeError("simulated API failure")
            return self._fake_nav(code)

        with mock.patch.object(NavStore, "_fetch_one", side_effect=fetch_side_effect):
            report = store.backfill(["001", "002", "003"])

        assert report.fetched == 2
        assert report.failed == 1
        assert "002" in report.failed_codes
        # Failed code has no data
        assert store.get_nav_series("002") == []
        assert store._get_progress("002") == "failed"
        # Others still got data
        assert len(store.get_nav_series("001")) == 5

    def test_backfill_idempotent_rerun(self, tmp_path):
        """Run backfill twice → second run all skipped, fetched=0."""
        store = NavStore(str(tmp_path / "nav.db"))
        codes = ["001", "002"]

        with mock.patch.object(NavStore, "_fetch_one", side_effect=[
            self._fake_nav("001"), self._fake_nav("002"),
        ]):
            report1 = store.backfill(codes)

        # Second run — _fetch_one should NOT be called (all skipped)
        with mock.patch.object(NavStore, "_fetch_one") as mock_fetch:
            report2 = store.backfill(codes)
            mock_fetch.assert_not_called()

        assert report1.fetched == 2
        assert report2.fetched == 0
        assert report2.skipped == 2

    def test_backfill_report_is_frozen_dataclass(self, tmp_path):
        """BackfillReport is a frozen dataclass (can't mutate fields)."""
        report = BackfillReport(
            fetched=1, skipped=0, failed=0, point_count=5, failed_codes=[]
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            report.fetched = 99

    def test_backfill_empty_codes_list(self, tmp_path):
        """Empty codes list → all-zero report, no crash."""
        store = NavStore(str(tmp_path / "nav.db"))
        report = store.backfill([])
        assert report.fetched == 0
        assert report.skipped == 0
        assert report.failed == 0
        assert report.point_count == 0


class TestUpdate:
    """Tests for NavStore.update() — gap detection + tiered recovery.

    Helper methods (_get_trading_dates, _fetch_daily_em, _fetch_one) are mocked
    so no live akshare calls are made. Tests verify gap detection logic and
    tiered recovery actions.
    """

    @staticmethod
    def _seed_nav(store: NavStore, code: str, dates: list[str], navs: list[float]):
        """Insert NAV points directly into fund_nav for testing."""
        for d, v in zip(dates, navs):
            store.append_nav(code, d, v)

    @staticmethod
    def _mock_trading_dates(dates: list[str]):
        """Mock _get_trading_dates to return a fixed list."""
        return mock.patch.object(NavStore, "_get_trading_dates", return_value=dates)

    @staticmethod
    def _mock_daily_em(rows: list[tuple[str, str, float]]):
        """Mock _fetch_daily_em to return fixed (code, date, unit_nav) rows."""
        return mock.patch.object(NavStore, "_fetch_daily_em", return_value=rows)

    def test_store_current_no_action(self, tmp_path):
        """Gap=0 → action='current', no fetch."""
        store = NavStore(str(tmp_path / "nav.db"))
        self._seed_nav(store, "001", ["2026-06-24"], [1.0])

        with self._mock_trading_dates(["2026-06-24"]), \
             self._mock_daily_em([]) as mock_daily:
            report = store.update()

        assert report.action == "current"
        assert report.gap_days == 0
        assert report.funds_updated == 0
        mock_daily.assert_not_called()

    def test_gap_le_2_triggers_bulk_update(self, tmp_path):
        """Gap=1 → action='bulk_update', _fetch_daily_em called, data inserted."""
        store = NavStore(str(tmp_path / "nav.db"))
        self._seed_nav(store, "001", ["2026-06-23"], [1.0])

        daily_rows = [("001", "2026-06-24", 1.01), ("002", "2026-06-24", 2.0)]
        with self._mock_trading_dates(["2026-06-23", "2026-06-24"]), \
             self._mock_daily_em(daily_rows):
            report = store.update()

        assert report.action == "bulk_update"
        assert report.gap_days == 1
        assert report.points_added >= 1
        # Data actually inserted
        assert 1.01 in store.get_nav_series("001", days=750)

    def test_gap_3_30_triggers_recovery_mode(self, tmp_path):
        """Gap=5 → action='recovery_mode', _recovery_needed flag set."""
        store = NavStore(str(tmp_path / "nav.db"))
        self._seed_nav(store, "001", ["2026-06-17"], [1.0])

        trading_dates = [f"2026-06-{d:02d}" for d in range(17, 25)]
        with self._mock_trading_dates(trading_dates), \
             self._mock_daily_em([]):
            report = store.update()

        assert report.action == "recovery_mode"
        # 8 dates (17-24), latest_db_date=17, 7 dates after → gap=7
        assert report.gap_days == 7

    def test_gap_gt_30_triggers_manual_backfill(self, tmp_path):
        """Gap>30 → action='manual_backfill_needed'."""
        store = NavStore(str(tmp_path / "nav.db"))
        self._seed_nav(store, "001", ["2026-05-01"], [1.0])

        # 35 trading dates from May 1 to Jun 24
        dates = [f"2026-05-{d:02d}" for d in range(1, 32)] + \
                [f"2026-06-{d:02d}" for d in range(1, 25)]
        with self._mock_trading_dates(dates), \
             self._mock_daily_em([]):
            report = store.update()

        assert report.action == "manual_backfill_needed"
        assert report.gap_days > 30

    def test_weekend_gap_counts_trading_days(self, tmp_path):
        """Fri(May 22) → Mon(May 25) = 1 trading day, not 3 calendar."""
        store = NavStore(str(tmp_path / "nav.db"))
        self._seed_nav(store, "001", ["2026-05-22"], [1.0])

        # Only trading dates: May 22 (Fri), May 25 (Mon), May 26 (Tue)
        with self._mock_trading_dates(["2026-05-22", "2026-05-25", "2026-05-26"]), \
             self._mock_daily_em([("001", "2026-05-25", 1.01), ("001", "2026-05-26", 1.02)]):
            report = store.update()

        # Gap = 2 trading days (May 25, May 26)
        assert report.action == "bulk_update"
        assert report.gap_days == 2

    def test_empty_store_triggers_manual_backfill(self, tmp_path):
        """No NAV data → gap is infinite → manual_backfill_needed."""
        store = NavStore(str(tmp_path / "nav.db"))
        with self._mock_trading_dates(["2026-06-24"]), \
             self._mock_daily_em([]):
            report = store.update()

        assert report.action == "manual_backfill_needed"
        assert report.latest_db_date is None

    def test_update_report_is_frozen_dataclass(self, tmp_path):
        """UpdateReport is a frozen dataclass."""
        report = UpdateReport(
            latest_db_date="2026-06-23",
            latest_trading_date="2026-06-24",
            gap_days=1,
            action="bulk_update",
            funds_updated=10,
            points_added=20,
        )
        with pytest.raises(Exception):
            report.action = "current"


class TestLazyRecovery:
    """Tests for lazy recovery during get_nav_series when _recovery_needed."""

    def test_recovery_mode_triggers_fetch_on_miss(self, tmp_path):
        """_recovery_needed + get_nav_series(missing_code) → _fetch_one called."""
        store = NavStore(str(tmp_path / "nav.db"))
        # Seed some data + set recovery mode
        store.append_nav("001", "2026-06-20", 1.0)
        store._recovery_needed = True

        fake_nav = [("2026-06-24", 1.05)]
        with mock.patch.object(NavStore, "_fetch_one", return_value=fake_nav) as mock_fetch:
            series = store.get_nav_series("002")  # "002" not in DB

        assert mock_fetch.called
        assert series == [1.05]  # data was fetched and returned

    def test_recovery_mode_skips_existing_codes(self, tmp_path):
        """_recovery_needed + get_nav_series(existing_code) → no fetch."""
        store = NavStore(str(tmp_path / "nav.db"))
        store.append_nav("001", "2026-06-20", 1.0)
        store.append_nav("001", "2026-06-21", 1.01)
        store._recovery_needed = True

        with mock.patch.object(NavStore, "_fetch_one") as mock_fetch:
            series = store.get_nav_series("001")

        mock_fetch.assert_not_called()
        assert series == [1.0, 1.01]

    def test_no_recovery_mode_no_lazy_fetch(self, tmp_path):
        """_recovery_needed=False + get_nav_series(missing_code) → no fetch, empty list."""
        store = NavStore(str(tmp_path / "nav.db"))
        # _recovery_needed defaults to False
        with mock.patch.object(NavStore, "_fetch_one") as mock_fetch:
            series = store.get_nav_series("999")

        mock_fetch.assert_not_called()
        assert series == []


class TestFetchDailyEmParsing:
    """Tests for _fetch_daily_em column parsing logic.

    The real fund_open_fund_daily_em returns columns like '2026-06-24-单位净值'
    (date embedded in column name). This tests the parsing without live API.
    """

    def test_parses_date_from_column_name(self):
        """Columns ending in '-单位净值' are parsed into (code, date, nav) rows."""
        import pandas as pd

        df = pd.DataFrame({
            "基金代码": ["001", "002"],
            "基金简称": ["FundA", "FundB"],
            "2026-06-24-单位净值": [1.01, 2.02],
            "2026-06-24-累计净值": [1.01, 2.02],
            "2026-06-23-单位净值": [1.00, 2.00],
            "2026-06-23-累计净值": [1.00, 2.00],
            "日增长值": [0.01, 0.02],
            "日增长率": [1.0, 1.0],
            "申购状态": ["开放", "开放"],
            "赎回状态": ["开放", "开放"],
            "手续费": ["0.00%", "0.00%"],
        })

        with mock.patch("akshare.fund_open_fund_daily_em", return_value=df):
            rows = NavStore._fetch_daily_em()

        # 2 dates × 2 funds = 4 rows
        assert len(rows) == 4
        # Check structure: (code, date, nav) — codes zero-padded to 6 digits
        codes = {r[0] for r in rows}
        dates = {r[1] for r in rows}
        assert codes == {"000001", "000002"}
        assert dates == {"2026-06-23", "2026-06-24"}
        # Check values
        nav_map = {(r[0], r[1]): r[2] for r in rows}
        assert nav_map[("000001", "2026-06-24")] == 1.01
        assert nav_map[("000002", "2026-06-23")] == 2.00

    def test_skips_nan_values(self):
        """NaN unit_nav values are skipped, not stored."""
        import pandas as pd

        df = pd.DataFrame({
            "基金代码": ["001", "002"],
            "2026-06-24-单位净值": [1.01, float("nan")],
        })

        with mock.patch("akshare.fund_open_fund_daily_em", return_value=df):
            rows = NavStore._fetch_daily_em()

        # Only 1 row (002's NaN skipped)
        assert len(rows) == 1
        assert rows[0] == ("000001", "2026-06-24", 1.01)

    def test_zfills_short_codes(self):
        """Fund codes are zero-padded to 6 digits (e.g. '1234' → '001234')."""
        import pandas as pd

        df = pd.DataFrame({
            "基金代码": ["1234"],
            "2026-06-24-单位净值": [1.0],
        })

        with mock.patch("akshare.fund_open_fund_daily_em", return_value=df):
            rows = NavStore._fetch_daily_em()

        assert rows[0][0] == "001234"
