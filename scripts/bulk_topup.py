"""One-shot bulk top-up using fund_open_fund_daily_em.

This endpoint returns the last 2 trading days (e.g. 2026-07-01 + 2026-06-30)
for ALL ~23k open-end funds in a single HTTP call. Each date is a separate
column ('2026-07-01-单位净值', '2026-06-30-单位净值', etc.).

Used to top up funds whose per-fund fetch (fund_open_fund_info_em) has a
1-2 day publication delay and missed the latest date(s).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import akshare as ak

from src.data.sources.nav_store import NavStore


def main() -> int:
    store = NavStore("data/market_cache.db")
    t0 = time.time()
    print("Calling ak.fund_open_fund_daily_em() ...", flush=True)
    df = ak.fund_open_fund_daily_em()
    print(f"  shape: {df.shape}  elapsed: {time.time() - t0:.1f}s", flush=True)

    date_cols = [c for c in df.columns if c.endswith("-单位净值")]
    print(f"  date columns: {date_cols}", flush=True)

    rows: list[tuple[str, str, float, None]] = []
    for col in date_cols:
        date_str = col.replace("-单位净值", "")
        for code, nav in zip(df["基金代码"], df[col]):
            if nav is None or str(nav) in ("nan", "", "None"):
                continue
            rows.append((str(code).zfill(6), date_str, float(nav), None))

    print(f"  total candidate rows: {len(rows)}", flush=True)

    before_per_date = {}
    for _, d, _, _ in rows:
        if d not in before_per_date:
            cnt = store._conn.execute(
                "SELECT COUNT(DISTINCT code) FROM fund_nav WHERE nav_date=?",
                (d,),
            ).fetchone()[0]
            before_per_date[d] = cnt

    store._conn.executemany(
        "INSERT OR IGNORE INTO fund_nav "
        "(code, nav_date, unit_nav, accum_nav) VALUES (?, ?, ?, ?)",
        rows,
    )
    store._conn.commit()

    print("\nCoverage after bulk top-up:")
    for d in sorted(before_per_date):
        cnt = store._conn.execute(
            "SELECT COUNT(DISTINCT code) FROM fund_nav WHERE nav_date=?",
            (d,),
        ).fetchone()[0]
        delta = cnt - before_per_date[d]
        print(f"  {d}: {cnt} (+{delta})")

    coverage = store.coverage_report()
    stats = store.stats()
    print("\nStore stats:")
    print(f"  Fund count:   {stats['fund_count']}")
    print(f"  Total points: {stats['total_points']}")
    print(f"  Date range:   {stats['date_range']}")
    print(f"  Latest date:  {coverage['latest_date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
