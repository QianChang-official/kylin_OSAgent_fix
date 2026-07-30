"""SQLite storage for metric samples.

Long format (ts, metric, value) rather than one column per metric so new
metrics need no schema migration. Retention is enforced per metric so one
fast-moving series cannot evict another's history.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from backend import config

DEFAULT_RETENTION_PER_METRIC = 2880  # 48h at one sample per minute


class MetricStore:
    def __init__(self, db_path: Path | None = None,
                 retention: int = DEFAULT_RETENTION_PER_METRIC) -> None:
        self.db_path = db_path or (config.PROJECT_DIR / "data" / "metrics.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention = retention
        self._lock = Lock()
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=5.0)

    def _ensure_table(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metric_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metric_ts ON metric_samples (metric, ts)"
            )
            conn.commit()

    def record(self, ts: float, values: dict[str, float | None]) -> int:
        """Persist one sample. None values are skipped, not stored as zero."""
        rows = [(ts, metric, float(value)) for metric, value in values.items() if value is not None]
        if not rows:
            return 0
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT INTO metric_samples (ts, metric, value) VALUES (?, ?, ?)", rows
            )
            conn.commit()
        return len(rows)

    def series(self, metric: str, limit: int = 240) -> list[dict[str, float]]:
        """Most recent samples for one metric, oldest first (chart order)."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, value FROM metric_samples WHERE metric = ? ORDER BY ts DESC LIMIT ?",
                (metric, max(1, limit)),
            ).fetchall()
        return [{"ts": row[0], "value": row[1]} for row in reversed(rows)]

    def values(self, metric: str, limit: int = 2880) -> list[float]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT value FROM metric_samples WHERE metric = ? ORDER BY ts DESC LIMIT ?",
                (metric, max(1, limit)),
            ).fetchall()
        return [row[0] for row in rows]

    def latest(self, metric: str) -> dict[str, float] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT ts, value FROM metric_samples WHERE metric = ? ORDER BY ts DESC LIMIT 1",
                (metric,),
            ).fetchone()
        return {"ts": row[0], "value": row[1]} if row else None

    def count(self, metric: str = "") -> int:
        with self._lock, self._connect() as conn:
            if metric:
                row = conn.execute(
                    "SELECT COUNT(*) FROM metric_samples WHERE metric = ?", (metric,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM metric_samples").fetchone()
        return int(row[0]) if row else 0

    def prune(self) -> int:
        """Trim each metric to the retention limit. Returns rows deleted."""
        with self._lock, self._connect() as conn:
            metrics = [row[0] for row in conn.execute(
                "SELECT DISTINCT metric FROM metric_samples"
            ).fetchall()]
            deleted = 0
            for metric in metrics:
                cursor = conn.execute(
                    """
                    DELETE FROM metric_samples
                    WHERE metric = ? AND id NOT IN (
                        SELECT id FROM metric_samples
                        WHERE metric = ? ORDER BY ts DESC LIMIT ?
                    )
                    """,
                    (metric, metric, self.retention),
                )
                deleted += cursor.rowcount or 0
            conn.commit()
        return deleted

    def clear(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM metric_samples")
            conn.commit()
