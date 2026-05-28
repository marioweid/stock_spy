"""Dashboard trade lifecycle models.

These models are intentionally independent of Streamlit so the same service layer can later be
used by FastAPI, a React frontend, or CLI tools.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

CandidateStatus = Literal["ACTIVE", "SKIPPED_UNTIL", "EXECUTED"]
PositionStatus = Literal[
    "OPEN",
    "STOP_REACHED",
    "TARGET_REACHED",
    "DEADLINE_REACHED",
    "CLOSED",
]
ExitReason = Literal["STOP", "TARGET", "DEADLINE", "MANUAL"]


class CandidateSnapshot(BaseModel):
    """A persisted dashboard-ready snapshot of a scanner candidate."""

    id: int | None = None
    ticker: str
    signature: str
    setup_kind: str
    currency: str
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    target: float = Field(gt=0)
    risk_reward: float = Field(gt=0)
    shares: int = Field(gt=0)
    cost: float = Field(gt=0)
    risk_amount: float = Field(ge=0)
    reward_amount: float = Field(ge=0)
    rationale: str
    earnings_warning: str | None = None
    status: CandidateStatus = "ACTIVE"
    skipped_until: datetime | None = None
    position_id: int | None = None
    created_at: datetime


class ExecutionInput(BaseModel):
    """User-confirmed external broker execution details."""

    actual_entry: float = Field(gt=0)
    shares: int = Field(gt=0)
    executed_at: datetime
    note: str = ""


class OpenPosition(BaseModel):
    """A trade the user already bought externally and now monitors here."""

    id: int | None = None
    candidate_id: int
    ticker: str
    currency: str
    shares: int = Field(gt=0)
    actual_entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    target: float = Field(gt=0)
    opened_at: datetime
    planned_entry: float = Field(gt=0)
    planned_shares: int = Field(gt=0)
    note: str = ""


class MonitoredPosition(BaseModel):
    """Open position plus current monitoring state for display."""

    position: OpenPosition
    status: PositionStatus
    current_price: float | None = None
    unrealized_pnl: float | None = None
    days_held: int


class ClosePositionInput(BaseModel):
    """User-confirmed external broker exit details."""

    exit_price: float = Field(gt=0)
    shares: int = Field(gt=0)
    exited_at: datetime
    exit_reason: ExitReason
    note: str = ""


class ClosedTrade(BaseModel):
    """Final immutable trade result for later performance analytics."""

    id: int | None = None
    position_id: int
    candidate_id: int
    ticker: str
    currency: str
    shares: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    opened_at: datetime
    exited_at: datetime
    exit_reason: ExitReason
    gross_pnl: float
    note: str = ""

    @model_validator(mode="after")
    def validate_exit_time(self) -> Self:
        """Ensure the trade cannot close before it opens."""
        if self.exited_at < self.opened_at:
            raise ValueError("Exit time cannot be before open time.")
        return self


def gross_pnl(position: OpenPosition, *, exit_price: float, shares: int) -> float:
    """Return gross P/L for a long position using actual entry and exit values."""
    if shares <= 0 or shares > position.shares:
        raise ValueError("Shares must be between 1 and the open position share count.")
    return round((exit_price - position.actual_entry) * shares, 2)
