"""SQLite-backed persistence for dashboard trade lifecycle state."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from swing_spy.trade_models import (
    CandidateSnapshot,
    ClosedTrade,
    ClosePositionInput,
    ExecutionInput,
    OpenPosition,
    gross_pnl,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboard_candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    signature TEXT NOT NULL UNIQUE,
    setup_kind TEXT NOT NULL,
    currency TEXT NOT NULL,
    entry REAL NOT NULL,
    stop REAL NOT NULL,
    target REAL NOT NULL,
    risk_reward REAL NOT NULL,
    shares INTEGER NOT NULL,
    cost REAL NOT NULL,
    risk_amount REAL NOT NULL,
    reward_amount REAL NOT NULL,
    rationale TEXT NOT NULL,
    earnings_warning TEXT,
    status TEXT NOT NULL,
    skipped_until TEXT,
    position_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS open_position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL UNIQUE,
    ticker TEXT NOT NULL,
    currency TEXT NOT NULL,
    shares INTEGER NOT NULL,
    actual_entry REAL NOT NULL,
    stop REAL NOT NULL,
    target REAL NOT NULL,
    opened_at TEXT NOT NULL,
    planned_entry REAL NOT NULL,
    planned_shares INTEGER NOT NULL,
    note TEXT NOT NULL,
    FOREIGN KEY(candidate_id) REFERENCES dashboard_candidate(id)
);
CREATE TABLE IF NOT EXISTS closed_trade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    currency TEXT NOT NULL,
    shares INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    opened_at TEXT NOT NULL,
    exited_at TEXT NOT NULL,
    exit_reason TEXT NOT NULL,
    gross_pnl REAL NOT NULL,
    note TEXT NOT NULL
);
"""


class TradeStore:
    """A thin repository over dashboard trade lifecycle tables."""

    def __init__(self, db_path: str) -> None:
        """Open and initialize the SQLite database at ``db_path``."""
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def upsert_candidate(self, candidate: CandidateSnapshot) -> int:
        """Insert or refresh a candidate snapshot by unique signature."""
        row = self._conn.execute(
            """
            INSERT INTO dashboard_candidate (
                ticker, signature, setup_kind, currency, entry, stop, target,
                risk_reward, shares, cost, risk_amount, reward_amount, rationale,
                earnings_warning, status, skipped_until, position_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signature) DO UPDATE SET
                ticker = excluded.ticker,
                setup_kind = excluded.setup_kind,
                currency = excluded.currency,
                entry = excluded.entry,
                stop = excluded.stop,
                target = excluded.target,
                risk_reward = excluded.risk_reward,
                shares = excluded.shares,
                cost = excluded.cost,
                risk_amount = excluded.risk_amount,
                reward_amount = excluded.reward_amount,
                rationale = excluded.rationale,
                earnings_warning = excluded.earnings_warning,
                created_at = excluded.created_at
            RETURNING id
            """,
            (
                candidate.ticker,
                candidate.signature,
                candidate.setup_kind,
                candidate.currency,
                candidate.entry,
                candidate.stop,
                candidate.target,
                candidate.risk_reward,
                candidate.shares,
                candidate.cost,
                candidate.risk_amount,
                candidate.reward_amount,
                candidate.rationale,
                candidate.earnings_warning,
                candidate.status,
                _optional_datetime(candidate.skipped_until),
                candidate.position_id,
                candidate.created_at.isoformat(),
            ),
        ).fetchone()
        self._conn.commit()
        return int(row["id"])

    def get_candidate(self, candidate_id: int) -> CandidateSnapshot | None:
        """Return one candidate snapshot by id, if present."""
        row = self._conn.execute(
            "SELECT * FROM dashboard_candidate WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return _candidate_from_row(row)

    def list_active_candidates(self, now: datetime) -> list[CandidateSnapshot]:
        """Return ACTIVE candidates and expired skipped candidates."""
        rows = self._conn.execute(
            """
            SELECT * FROM dashboard_candidate
            WHERE status = 'ACTIVE'
               OR (status = 'SKIPPED_UNTIL' AND skipped_until <= ?)
            ORDER BY id
            """,
            (now.isoformat(),),
        ).fetchall()
        return [_candidate_from_row(row) for row in rows]

    def skip_candidate(self, candidate_id: int, skipped_until: datetime) -> None:
        """Hide a candidate until the provided expiry timestamp."""
        self._conn.execute(
            """
            UPDATE dashboard_candidate
            SET status = 'SKIPPED_UNTIL', skipped_until = ?
            WHERE id = ?
            """,
            (skipped_until.isoformat(), candidate_id),
        )
        self._conn.commit()

    def create_open_position(
        self,
        candidate_id: int,
        execution: ExecutionInput,
    ) -> OpenPosition:
        """Create an open position from an active candidate snapshot."""
        candidate = self.get_candidate(candidate_id)
        if candidate is None or not _is_active_candidate(candidate, execution.executed_at):
            raise ValueError(f"Candidate {candidate_id} is not active.")

        row = self._conn.execute(
            """
            INSERT INTO open_position (
                candidate_id, ticker, currency, shares, actual_entry, stop, target,
                opened_at, planned_entry, planned_shares, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                candidate_id,
                candidate.ticker,
                candidate.currency,
                execution.shares,
                execution.actual_entry,
                candidate.stop,
                candidate.target,
                execution.executed_at.isoformat(),
                candidate.entry,
                candidate.shares,
                execution.note,
            ),
        ).fetchone()
        position = _position_from_row(row)
        self._conn.execute(
            """
            UPDATE dashboard_candidate
            SET status = 'EXECUTED', position_id = ?
            WHERE id = ?
            """,
            (position.id, candidate_id),
        )
        self._conn.commit()
        return position

    def list_open_positions(self) -> list[OpenPosition]:
        """Return all currently open positions."""
        rows = self._conn.execute("SELECT * FROM open_position ORDER BY id").fetchall()
        return [_position_from_row(row) for row in rows]

    def close_position(
        self,
        position_id: int,
        close_input: ClosePositionInput,
    ) -> ClosedTrade:
        """Move an open position into the closed trade ledger."""
        position = self._get_open_position(position_id)
        if position is None:
            raise ValueError(f"Position {position_id} is not open.")
        if close_input.shares != position.shares:
            raise ValueError("Closing share count must match the open position share count.")

        pnl = gross_pnl(
            position,
            exit_price=close_input.exit_price,
            shares=close_input.shares,
        )
        row = self._conn.execute(
            """
            INSERT INTO closed_trade (
                position_id, candidate_id, ticker, currency, shares, entry_price,
                exit_price, opened_at, exited_at, exit_reason, gross_pnl, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                position_id,
                position.candidate_id,
                position.ticker,
                position.currency,
                close_input.shares,
                position.actual_entry,
                close_input.exit_price,
                position.opened_at.isoformat(),
                close_input.exited_at.isoformat(),
                close_input.exit_reason,
                pnl,
                close_input.note,
            ),
        ).fetchone()
        self._conn.execute("DELETE FROM open_position WHERE id = ?", (position_id,))
        self._conn.commit()
        return _closed_trade_from_row(row)

    def list_closed_trades(self) -> list[ClosedTrade]:
        """Return the immutable closed trade ledger."""
        rows = self._conn.execute("SELECT * FROM closed_trade ORDER BY id").fetchall()
        return [_closed_trade_from_row(row) for row in rows]

    def _get_open_position(self, position_id: int) -> OpenPosition | None:
        row = self._conn.execute(
            "SELECT * FROM open_position WHERE id = ?",
            (position_id,),
        ).fetchone()
        if row is None:
            return None
        return _position_from_row(row)


def _candidate_from_row(row: sqlite3.Row) -> CandidateSnapshot:
    return CandidateSnapshot(
        id=int(row["id"]),
        ticker=str(row["ticker"]),
        signature=str(row["signature"]),
        setup_kind=str(row["setup_kind"]),
        currency=str(row["currency"]),
        entry=float(row["entry"]),
        stop=float(row["stop"]),
        target=float(row["target"]),
        risk_reward=float(row["risk_reward"]),
        shares=int(row["shares"]),
        cost=float(row["cost"]),
        risk_amount=float(row["risk_amount"]),
        reward_amount=float(row["reward_amount"]),
        rationale=str(row["rationale"]),
        earnings_warning=_optional_text(row["earnings_warning"]),
        status=row["status"],
        skipped_until=_optional_datetime_from_row(row["skipped_until"]),
        position_id=_optional_int(row["position_id"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _position_from_row(row: sqlite3.Row) -> OpenPosition:
    return OpenPosition(
        id=int(row["id"]),
        candidate_id=int(row["candidate_id"]),
        ticker=str(row["ticker"]),
        currency=str(row["currency"]),
        shares=int(row["shares"]),
        actual_entry=float(row["actual_entry"]),
        stop=float(row["stop"]),
        target=float(row["target"]),
        opened_at=datetime.fromisoformat(str(row["opened_at"])),
        planned_entry=float(row["planned_entry"]),
        planned_shares=int(row["planned_shares"]),
        note=str(row["note"]),
    )


def _closed_trade_from_row(row: sqlite3.Row) -> ClosedTrade:
    return ClosedTrade(
        id=int(row["id"]),
        position_id=int(row["position_id"]),
        candidate_id=int(row["candidate_id"]),
        ticker=str(row["ticker"]),
        currency=str(row["currency"]),
        shares=int(row["shares"]),
        entry_price=float(row["entry_price"]),
        exit_price=float(row["exit_price"]),
        opened_at=datetime.fromisoformat(str(row["opened_at"])),
        exited_at=datetime.fromisoformat(str(row["exited_at"])),
        exit_reason=row["exit_reason"],
        gross_pnl=float(row["gross_pnl"]),
        note=str(row["note"]),
    )


def _is_active_candidate(candidate: CandidateSnapshot, now: datetime) -> bool:
    if candidate.status == "ACTIVE":
        return True
    if candidate.status != "SKIPPED_UNTIL" or candidate.skipped_until is None:
        return False
    return candidate.skipped_until <= now


def _optional_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _optional_datetime_from_row(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
