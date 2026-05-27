"""SQLite-backed state for the scanner: per-ticker alert dedup and an alert log.

A standing setup would otherwise re-notify every cycle. Each candidate carries a signature
(trade date + rounded entry/stop); the scanner alerts only when a ticker's signature changes,
so the same setup on the same day is sent once, but a fresh day or shifted levels alert again.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_alert (
    ticker      TEXT PRIMARY KEY,
    signature   TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker     TEXT NOT NULL,
    kind       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Store:
    """A thin repository over a SQLite database file for scanner state."""

    def __init__(self, db_path: str) -> None:
        """Open (and create if needed) the database at ``db_path`` (or ``":memory:"``)."""
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def is_new_signature(self, ticker: str, signature: str) -> bool:
        """Return whether this candidate signature differs from the last one alerted."""
        row = self._conn.execute(
            "SELECT signature FROM candidate_alert WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        return row is None or row["signature"] != signature

    def record_alert(self, ticker: str, signature: str, kind: str) -> None:
        """Persist the alerted signature for a ticker and append to the alert log."""
        now = _now()
        self._conn.execute(
            """
            INSERT INTO candidate_alert (ticker, signature, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                signature = excluded.signature,
                updated_at = excluded.updated_at
            """,
            (ticker, signature, now),
        )
        self._conn.execute(
            "INSERT INTO alert_log (ticker, kind, created_at) VALUES (?, ?, ?)",
            (ticker, kind, now),
        )
        self._conn.commit()

    def alert_count(self, ticker: str) -> int:
        """Return how many alerts have been logged for a ticker."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM alert_log WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        return int(row["n"])


def _now() -> str:
    """Current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()
