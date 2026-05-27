"""SQLite-backed state: price-alert baselines, news dedup, and an alert log."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from signal_spy.models import Signal
from spy_core.models import NewsItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_baseline (
    ticker        TEXT PRIMARY KEY,
    previous_close REAL NOT NULL,
    alerted       INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seen_news (
    dedup_key   TEXT PRIMARY KEY,
    ticker      TEXT NOT NULL,
    first_seen  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker     TEXT NOT NULL,
    signal     TEXT NOT NULL,
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class PriceBaseline:
    """The previous close we last recorded for a ticker and whether we alerted on it."""

    previous_close: float
    alerted: bool


class Store:
    """A thin repository over a SQLite database file.

    The database persists across restarts so the service does not re-alert on
    price moves or news it has already reported.
    """

    def __init__(self, db_path: str) -> None:
        """Open (and create if needed) the database at ``db_path``.

        Args:
            db_path: Filesystem path, or ``":memory:"`` for an ephemeral DB.
        """
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def get_price_baseline(self, ticker: str) -> PriceBaseline | None:
        """Return the stored baseline for a ticker, or ``None`` if unseen."""
        row = self._conn.execute(
            "SELECT previous_close, alerted FROM price_baseline WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if row is None:
            return None
        return PriceBaseline(previous_close=row["previous_close"], alerted=bool(row["alerted"]))

    def set_price_baseline(self, ticker: str, previous_close: float, *, alerted: bool) -> None:
        """Upsert the baseline previous close and alerted flag for a ticker."""
        self._conn.execute(
            """
            INSERT INTO price_baseline (ticker, previous_close, alerted, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                previous_close = excluded.previous_close,
                alerted = excluded.alerted,
                updated_at = excluded.updated_at
            """,
            (ticker, previous_close, int(alerted), _now()),
        )
        self._conn.commit()

    def unseen_news(self, items: Iterable[NewsItem]) -> list[NewsItem]:
        """Return only the items whose dedup key is not yet recorded as seen."""
        result: list[NewsItem] = []
        for item in items:
            row = self._conn.execute(
                "SELECT 1 FROM seen_news WHERE dedup_key = ?",
                (item.dedup_key(),),
            ).fetchone()
            if row is None:
                result.append(item)
        return result

    def mark_news_seen(self, items: Iterable[NewsItem]) -> None:
        """Record the given items as seen so they are not processed again."""
        now = _now()
        self._conn.executemany(
            "INSERT OR IGNORE INTO seen_news (dedup_key, ticker, first_seen) VALUES (?, ?, ?)",
            [(item.dedup_key(), item.ticker, now) for item in items],
        )
        self._conn.commit()

    def record_alert(self, ticker: str, signal: Signal, reason: str) -> None:
        """Append an entry to the alert log."""
        self._conn.execute(
            "INSERT INTO alert_log (ticker, signal, reason, created_at) VALUES (?, ?, ?, ?)",
            (ticker, signal, reason, _now()),
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
