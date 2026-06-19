"""Local SQLite-based cache for market data.

TTL-based expiry. Used as final fallback in MarketDataFacade chain.
"""
import sqlite3
import time


class MarketCache:
    """Key-value cache with TTL, backed by SQLite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_cache (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                cached_at REAL NOT NULL,
                ttl_seconds INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, key: str) -> str | None:
        """Return cached data if valid (non-expired), or None."""
        now = time.time()
        row = self._conn.execute(
            "SELECT data, cached_at, ttl_seconds FROM market_cache WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        _data, cached_at, ttl_seconds = row
        if now - cached_at > ttl_seconds:
            # Expired — clean up
            self._conn.execute("DELETE FROM market_cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return _data

    def set(self, key: str, data: str, ttl_seconds: int) -> None:
        """Store data with TTL. Upsert on key conflict."""
        now = time.time()
        self._conn.execute(
            """
            INSERT INTO market_cache (key, data, cached_at, ttl_seconds)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                data = excluded.data,
                cached_at = excluded.cached_at,
                ttl_seconds = excluded.ttl_seconds
            """,
            (key, data, now, ttl_seconds),
        )
        self._conn.commit()

    def invalidate(self, key_pattern: str) -> int:
        """Delete all keys matching LIKE pattern. Returns count deleted."""
        cursor = self._conn.execute(
            "DELETE FROM market_cache WHERE key LIKE ?", (key_pattern,)
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MarketCache":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        self.close()
        return False

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
