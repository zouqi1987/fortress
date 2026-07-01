"""Sequential backfill driver that bypasses concurrent V8/mini_racer crash on macOS.

The default NavStore.backfill() uses ThreadPoolExecutor with 5 workers.
Each worker calls ak.fund_open_fund_info_em(), which initializes an embedded
V8 engine (py-mini-racer). On macOS, concurrent V8 init in worker threads
crashes with:
  [FATAL:address_pool_manager.cc(67)] Check failed: !pool->IsInitialized().

This script does the same backfill serially, which is slower (no concurrency
benefit) but stable. Expected runtime: ~30-60 min for 23k funds.

It re-uses the existing backfill infrastructure (idempotent + resumable):
- Skips codes already marked 'done' (use --force to refetch)
- Updates nav_backfill_progress on each success/failure
"""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.sources.nav_store import NavStore


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/market_cache.db")
    p.add_argument("--period", default="3年")
    p.add_argument("--force", action="store_true",
                   help="Re-fetch even for codes already marked done")
    p.add_argument("--codes-from-progress", action="store_true",
                   help="Use codes already in nav_backfill_progress (skip akshare rank/daily)")
    args = p.parse_args()

    store = NavStore(args.db)

    if args.codes_from_progress:
        rows = store._conn.execute(
            "SELECT code FROM nav_backfill_progress"
        ).fetchall()
        codes = sorted({r[0] for r in rows})
        print(f"Using {len(codes)} codes from nav_backfill_progress", flush=True)
    else:
        print("Fetching all fund codes (rank + daily endpoints)...", flush=True)
        codes = NavStore._get_all_fund_codes()
        print(f"Got {len(codes)} codes", flush=True)

    if args.force:
        store._conn.execute(
            "UPDATE nav_backfill_progress SET status='pending' "
            "WHERE status='done'"
        )
        store._conn.commit()
        print("Force mode: marked all done → pending", flush=True)

    # Init progress for new codes (idempotent)
    for code in codes:
        store._conn.execute(
            "INSERT OR IGNORE INTO nav_backfill_progress (code, status) "
            "VALUES (?, 'pending')",
            (code,),
        )
    store._conn.commit()

    to_fetch = [c for c in codes
                if store._get_progress(c) != "done"]
    skipped = len(codes) - len(to_fetch)
    print(f"Skipping {skipped} done; need to fetch {len(to_fetch)}",
          flush=True)

    fetched = failed = total_points = 0
    failed_codes: list[str] = []
    t0 = time.time()

    for i, code in enumerate(to_fetch, 1):
        try:
            nav_points = NavStore._fetch_one(code, args.period)
            store._conn.executemany(
                "INSERT OR IGNORE INTO fund_nav "
                "(code, nav_date, unit_nav, accum_nav) VALUES (?, ?, ?, ?)",
                [(code, d, v, None) for d, v in nav_points],
            )
            store._conn.execute(
                "UPDATE nav_backfill_progress SET status='done', "
                "fetched_at=?, point_count=? WHERE code=?",
                (datetime.now().isoformat(), len(nav_points), code),
            )
            store._conn.commit()
            fetched += 1
            total_points += len(nav_points)
        except Exception as e:
            store._conn.execute(
                "UPDATE nav_backfill_progress SET status='failed' "
                "WHERE code=?",
                (code,),
            )
            store._conn.commit()
            failed += 1
            failed_codes.append(code)
            print(f"  FAILED {code}: {e}", flush=True)

        if i % 50 == 0 or i == len(to_fetch):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(to_fetch) - i) / rate if rate > 0 else 0
            print(
                f"  [{i}/{len(to_fetch)}] "
                f"ok={fetched} fail={failed} pts={total_points} "
                f"elapsed={elapsed:.0f}s rate={rate:.2f}/s eta={eta:.0f}s",
                flush=True,
            )

    print("\nBackfill complete:")
    print(f"  Fetched:     {fetched}")
    print(f"  Skipped:     {skipped}")
    print(f"  Failed:      {failed}")
    print(f"  Points:      {total_points}")
    if failed_codes:
        print(f"  Failed codes (first 20): {failed_codes[:20]}")

    stats = store.stats()
    coverage = store.coverage_report()
    print("\nStore stats:")
    print(f"  Fund count:   {stats['fund_count']}")
    print(f"  Total points: {stats['total_points']}")
    print(f"  Date range:   {stats['date_range']}")
    print(f"  Latest date:  {coverage['latest_date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
