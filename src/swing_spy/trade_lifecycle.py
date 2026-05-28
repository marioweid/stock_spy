"""Business service for dashboard candidate and position lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from swing_spy.trade_models import (
    CandidateSnapshot,
    ClosedTrade,
    ClosePositionInput,
    ExecutionInput,
    MonitoredPosition,
    OpenPosition,
    PositionStatus,
)
from swing_spy.trade_store import TradeStore

PriceLookup = Callable[[str], float | None]
Clock = Callable[[], datetime]

_SKIP_DAYS = 1
_MAX_HOLDING_DAYS = 10


class TradeLifecycleService:
    """Coordinates candidate and position lifecycle operations."""

    def __init__(self, store: TradeStore, *, clock: Clock | None = None) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(UTC))

    def close(self) -> None:
        """Close the underlying store."""
        self.store.close()

    def record_candidate(self, candidate: CandidateSnapshot) -> int:
        """Persist or refresh a dashboard candidate snapshot."""
        return self.store.upsert_candidate(candidate)

    def list_candidates(self) -> list[CandidateSnapshot]:
        """Return active candidates visible at the current time."""
        return self.store.list_active_candidates(self.clock())

    def skip_candidate(self, candidate_id: int) -> None:
        """Hide a candidate for one day."""
        self.store.skip_candidate(
            candidate_id,
            self.clock() + timedelta(days=_SKIP_DAYS),
        )

    def execute_candidate(
        self,
        candidate_id: int,
        execution: ExecutionInput,
    ) -> OpenPosition:
        """Create an open position from a user-confirmed external broker fill."""
        return self.store.create_open_position(candidate_id, execution)

    def list_open_positions(self, price_lookup: PriceLookup) -> list[MonitoredPosition]:
        """Return open positions with advisory monitoring state."""
        positions = self.store.list_open_positions()
        return [
            self._monitor(position, price_lookup(position.ticker))
            for position in positions
        ]

    def close_position(
        self,
        position_id: int,
        close_input: ClosePositionInput,
    ) -> ClosedTrade:
        """Close a position after the user confirms the external broker sale."""
        return self.store.close_position(position_id, close_input)

    def _monitor(
        self,
        position: OpenPosition,
        current_price: float | None,
    ) -> MonitoredPosition:
        days_held = max((self.clock().date() - position.opened_at.date()).days, 0)
        status = _position_status(position, current_price, days_held)
        unrealized = None
        if current_price is not None:
            unrealized = round((current_price - position.actual_entry) * position.shares, 2)
        return MonitoredPosition(
            position=position,
            status=status,
            current_price=current_price,
            unrealized_pnl=unrealized,
            days_held=days_held,
        )


def _position_status(
    position: OpenPosition,
    current_price: float | None,
    days_held: int,
) -> PositionStatus:
    if current_price is not None and current_price <= position.stop:
        return "STOP_REACHED"
    if current_price is not None and current_price >= position.target:
        return "TARGET_REACHED"
    if days_held >= _MAX_HOLDING_DAYS:
        return "DEADLINE_REACHED"
    return "OPEN"
