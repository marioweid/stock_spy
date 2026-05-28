# Swing Dashboard MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Streamlit dashboard that displays `swing_spy` candidates, records user-confirmed executions, monitors open positions, and closes trades only after user confirmation.

**Architecture:** Keep Streamlit physically isolated in `src/swing_spy/streamlit_app/`. All trade state, validation, persistence, monitoring, and P/L logic lives in plain Python service modules under `src/swing_spy/` so FastAPI or a React frontend can reuse it later. The existing scanner writes dashboard candidate snapshots into the same SQLite database; the Streamlit app reads and mutates those snapshots through services.

**Tech Stack:** Python 3.13, Pydantic, SQLite, yfinance-backed existing price/history providers, Streamlit 1.57.0, pytest, ruff, ty.

---

## File Structure

- Create `src/swing_spy/trade_models.py`
  - Pydantic models and literal status types for dashboard candidates, open positions, closed trades, execution input, close input, and monitored position views.
- Create `tests/swing_spy/test_trade_models.py`
  - Validation tests for status values, execution values, close values, and P/L behavior.
- Create `src/swing_spy/trade_store.py`
  - SQLite repository for dashboard candidate snapshots, open positions, and closed trades.
- Create `tests/swing_spy/test_trade_store.py`
  - Persistence and state-transition tests using `:memory:`.
- Create `src/swing_spy/trade_lifecycle.py`
  - Service layer for listing candidates, skipping candidates, executing candidates, evaluating open position trigger states, and closing positions.
- Create `tests/swing_spy/test_trade_lifecycle.py`
  - Behavior tests for human-in-the-loop lifecycle rules.
- Create `src/swing_spy/position_pricing.py`
  - Price lookup adapter for open positions, using existing `download_history` and `quote_from_frame` patterns.
- Create `tests/swing_spy/test_position_pricing.py`
  - Price adapter tests with injected history function.
- Modify `src/swing_spy/scanner.py`
  - Add optional dashboard candidate recorder callback.
- Create `src/swing_spy/dashboard_candidates.py`
  - Convert `report.Candidate` into `trade_models.CandidateSnapshot`.
- Create `tests/swing_spy/test_dashboard_candidates.py`
  - Candidate conversion and scanner recording tests.
- Modify `pyproject.toml`
  - Add `streamlit==1.57.0`.
- Modify `uv.lock`
  - Regenerate with `uv lock`.
- Create `src/swing_spy/streamlit_app/__init__.py`
  - Package marker for UI-only code.
- Create `src/swing_spy/streamlit_app/app.py`
  - Streamlit entrypoint and page layout.
- Create `src/swing_spy/streamlit_app/components.py`
  - Card and form rendering helpers.
- Create `src/swing_spy/streamlit_app/service_factory.py`
  - Streamlit-only cached service construction from `swing_config.toml`.
- Create `tests/swing_spy/test_streamlit_boundary.py`
  - Import-boundary test proving non-UI service modules do not import Streamlit.
- Modify `README.md`
  - Add dashboard run instructions.

## Task 1: Trade Models

**Files:**
- Create: `src/swing_spy/trade_models.py`
- Create: `tests/swing_spy/test_trade_models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/swing_spy/test_trade_models.py`:

```python
"""Tests for dashboard trade lifecycle models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from swing_spy.trade_models import (
    CandidateSnapshot,
    ClosePositionInput,
    ExecutionInput,
    OpenPosition,
    gross_pnl,
)


def test_execution_input_requires_positive_values() -> None:
    with pytest.raises(ValidationError):
        ExecutionInput(actual_entry=0.0, shares=10, executed_at=_dt())

    with pytest.raises(ValidationError):
        ExecutionInput(actual_entry=100.0, shares=0, executed_at=_dt())


def test_close_input_requires_positive_values() -> None:
    with pytest.raises(ValidationError):
        ClosePositionInput(exit_price=0.0, shares=10, exited_at=_dt(), exit_reason="TARGET")

    with pytest.raises(ValidationError):
        ClosePositionInput(exit_price=120.0, shares=0, exited_at=_dt(), exit_reason="TARGET")


def test_candidate_snapshot_carries_original_plan() -> None:
    candidate = CandidateSnapshot(
        ticker="MUV2.DE",
        signature="2026-05-28:468.0:458.0",
        setup_kind="pullback",
        currency="EUR",
        entry=468.0,
        stop=458.0,
        target=492.0,
        risk_reward=2.4,
        shares=10,
        cost=4680.0,
        risk_amount=100.0,
        reward_amount=240.0,
        rationale="Pulled back toward support.",
        earnings_warning=None,
        created_at=_dt(),
    )

    assert candidate.status == "ACTIVE"
    assert candidate.ticker == "MUV2.DE"
    assert candidate.target == 492.0


def test_gross_pnl_uses_actual_values() -> None:
    position = OpenPosition(
        id=1,
        candidate_id=7,
        ticker="MUV2.DE",
        currency="EUR",
        shares=10,
        actual_entry=468.0,
        stop=458.0,
        target=492.0,
        opened_at=_dt(),
        planned_entry=470.0,
        planned_shares=9,
    )

    assert gross_pnl(position, exit_price=492.0, shares=10) == 240.0


def _dt() -> datetime:
    return datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```bash
uv run pytest -q tests/swing_spy/test_trade_models.py
```

Expected: fail with `ModuleNotFoundError: No module named 'swing_spy.trade_models'`.

- [ ] **Step 3: Implement trade models**

Create `src/swing_spy/trade_models.py`:

```python
"""Dashboard trade lifecycle models.

These models are intentionally independent of Streamlit so the same service layer can later be
used by FastAPI, a React frontend, or CLI tools.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CandidateStatus = Literal["ACTIVE", "SKIPPED_UNTIL", "EXECUTED"]
PositionStatus = Literal["OPEN", "STOP_REACHED", "TARGET_REACHED", "DEADLINE_REACHED", "CLOSED"]
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


def gross_pnl(position: OpenPosition, *, exit_price: float, shares: int) -> float:
    """Return gross P/L for a long position using actual entry and exit values."""
    return round((exit_price - position.actual_entry) * shares, 2)
```

- [ ] **Step 4: Run model tests to verify they pass**

Run:

```bash
uv run pytest -q tests/swing_spy/test_trade_models.py
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/swing_spy/trade_models.py tests/swing_spy/test_trade_models.py
git commit -m "Add dashboard trade models"
```

## Task 2: SQLite Trade Store

**Files:**
- Create: `src/swing_spy/trade_store.py`
- Create: `tests/swing_spy/test_trade_store.py`

- [ ] **Step 1: Write failing store tests**

Create `tests/swing_spy/test_trade_store.py`:

```python
"""Tests for dashboard trade persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from swing_spy.trade_models import CandidateSnapshot, ClosePositionInput, ExecutionInput
from swing_spy.trade_store import TradeStore


def test_candidate_upsert_and_active_listing() -> None:
    store = TradeStore(":memory:")
    candidate_id = store.upsert_candidate(_candidate())

    active = store.list_active_candidates(_dt())

    assert candidate_id == 1
    assert [c.ticker for c in active] == ["MUV2.DE"]
    store.close()


def test_skipped_candidate_is_hidden_until_expiry() -> None:
    store = TradeStore(":memory:")
    candidate_id = store.upsert_candidate(_candidate())
    store.skip_candidate(candidate_id, _dt() + timedelta(days=1))

    assert store.list_active_candidates(_dt()) == []
    assert [c.id for c in store.list_active_candidates(_dt() + timedelta(days=2))] == [
        candidate_id
    ]
    store.close()


def test_execute_candidate_creates_position_and_hides_candidate() -> None:
    store = TradeStore(":memory:")
    candidate_id = store.upsert_candidate(_candidate())

    position = store.create_open_position(
        candidate_id,
        ExecutionInput(actual_entry=469.0, shares=9, executed_at=_dt(), note="filled"),
    )

    candidate = store.get_candidate(candidate_id)
    assert position.id == 1
    assert position.actual_entry == 469.0
    assert position.planned_entry == 468.0
    assert position.planned_shares == 10
    assert candidate is not None
    assert candidate.status == "EXECUTED"
    assert candidate.position_id == position.id
    assert store.list_active_candidates(_dt()) == []
    store.close()


def test_close_position_writes_closed_trade_and_removes_open_position() -> None:
    store = TradeStore(":memory:")
    candidate_id = store.upsert_candidate(_candidate())
    position = store.create_open_position(
        candidate_id,
        ExecutionInput(actual_entry=468.0, shares=10, executed_at=_dt()),
    )

    assert position.id is not None
    closed = store.close_position(
        position.id,
        ClosePositionInput(
            exit_price=492.0,
            shares=10,
            exited_at=_dt() + timedelta(days=5),
            exit_reason="TARGET",
            note="sold in broker",
        ),
    )

    assert closed.gross_pnl == 240.0
    assert store.list_open_positions() == []
    assert store.list_closed_trades()[0].exit_reason == "TARGET"
    store.close()


def _candidate() -> CandidateSnapshot:
    return CandidateSnapshot(
        ticker="MUV2.DE",
        signature="2026-05-28:468.0:458.0",
        setup_kind="pullback",
        currency="EUR",
        entry=468.0,
        stop=458.0,
        target=492.0,
        risk_reward=2.4,
        shares=10,
        cost=4680.0,
        risk_amount=100.0,
        reward_amount=240.0,
        rationale="Pulled back toward support.",
        earnings_warning=None,
        created_at=_dt(),
    )


def _dt() -> datetime:
    return datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
```

- [ ] **Step 2: Run store tests to verify they fail**

Run:

```bash
uv run pytest -q tests/swing_spy/test_trade_store.py
```

Expected: fail with `ModuleNotFoundError: No module named 'swing_spy.trade_store'`.

- [ ] **Step 3: Implement the trade store**

Create `src/swing_spy/trade_store.py` with these public methods and schema:

```python
"""SQLite repository for dashboard candidates, open positions, and closed trades."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

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
```

Implement `TradeStore` with the public methods called by the tests:

- `__init__(self, db_path: str) -> None`
- `close(self) -> None`
- `upsert_candidate(self, candidate: CandidateSnapshot) -> int`
- `get_candidate(self, candidate_id: int) -> CandidateSnapshot | None`
- `list_active_candidates(self, now: datetime) -> list[CandidateSnapshot]`
- `skip_candidate(self, candidate_id: int, skipped_until: datetime) -> None`
- `create_open_position(self, candidate_id: int, execution: ExecutionInput) -> OpenPosition`
- `list_open_positions(self) -> list[OpenPosition]`
- `close_position(self, position_id: int, close_input: ClosePositionInput) -> ClosedTrade`
- `list_closed_trades(self) -> list[ClosedTrade]`

Use `datetime.isoformat()` for writes and `datetime.fromisoformat(value)` for reads. Raise
`ValueError("Candidate <id> is not active.")` when executing a missing, skipped, or executed
candidate. Raise `ValueError("Position <id> is not open.")` when closing a missing position.

- [ ] **Step 4: Run store tests to verify they pass**

Run:

```bash
uv run pytest -q tests/swing_spy/test_trade_store.py
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/swing_spy/trade_store.py tests/swing_spy/test_trade_store.py
git commit -m "Add dashboard trade store"
```

## Task 3: Trade Lifecycle Service

**Files:**
- Create: `src/swing_spy/trade_lifecycle.py`
- Create: `tests/swing_spy/test_trade_lifecycle.py`

- [ ] **Step 1: Write failing lifecycle tests**

Create `tests/swing_spy/test_trade_lifecycle.py`:

```python
"""Tests for dashboard trade lifecycle services."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from swing_spy.trade_lifecycle import TradeLifecycleService
from swing_spy.trade_models import CandidateSnapshot, ClosePositionInput, ExecutionInput
from swing_spy.trade_store import TradeStore


def test_skip_hides_candidate_for_one_day() -> None:
    service = _service()
    candidate_id = service.record_candidate(_candidate())

    service.skip_candidate(candidate_id)

    assert service.list_candidates() == []
    service.clock = lambda: _dt() + timedelta(days=2)
    assert service.list_candidates()[0].id == candidate_id
    service.close()


def test_execute_candidate_requires_user_input_and_creates_open_position() -> None:
    service = _service()
    candidate_id = service.record_candidate(_candidate())

    position = service.execute_candidate(
        candidate_id,
        ExecutionInput(actual_entry=469.0, shares=9, executed_at=_dt()),
    )

    assert position.actual_entry == 469.0
    assert position.shares == 9
    assert service.list_candidates() == []
    assert service.list_open_positions(lambda _ticker: 469.0)[0].status == "OPEN"
    service.close()


def test_monitoring_flags_do_not_close_position() -> None:
    service = _service()
    candidate_id = service.record_candidate(_candidate())
    service.execute_candidate(candidate_id, ExecutionInput(actual_entry=468.0, shares=10, executed_at=_dt()))

    monitored = service.list_open_positions(lambda _ticker: 457.0)

    assert monitored[0].status == "STOP_REACHED"
    assert service.store.list_closed_trades() == []
    assert len(service.store.list_open_positions()) == 1
    service.close()


def test_target_and_deadline_states_are_reported() -> None:
    service = _service()
    candidate_id = service.record_candidate(_candidate())
    service.execute_candidate(candidate_id, ExecutionInput(actual_entry=468.0, shares=10, executed_at=_dt()))

    target = service.list_open_positions(lambda _ticker: 493.0)[0]
    service.clock = lambda: _dt() + timedelta(days=11)
    deadline = service.list_open_positions(lambda _ticker: 480.0)[0]

    assert target.status == "TARGET_REACHED"
    assert deadline.status == "DEADLINE_REACHED"
    service.close()


def test_close_position_requires_explicit_command() -> None:
    service = _service()
    candidate_id = service.record_candidate(_candidate())
    position = service.execute_candidate(
        candidate_id,
        ExecutionInput(actual_entry=468.0, shares=10, executed_at=_dt()),
    )

    assert position.id is not None
    closed = service.close_position(
        position.id,
        ClosePositionInput(
            exit_price=492.0,
            shares=10,
            exited_at=_dt() + timedelta(days=5),
            exit_reason="TARGET",
        ),
    )

    assert closed.gross_pnl == 240.0
    assert service.store.list_open_positions() == []
    service.close()


def _service() -> TradeLifecycleService:
    return TradeLifecycleService(TradeStore(":memory:"), clock=_dt)


def _candidate() -> CandidateSnapshot:
    return CandidateSnapshot(
        ticker="MUV2.DE",
        signature="2026-05-28:468.0:458.0",
        setup_kind="pullback",
        currency="EUR",
        entry=468.0,
        stop=458.0,
        target=492.0,
        risk_reward=2.4,
        shares=10,
        cost=4680.0,
        risk_amount=100.0,
        reward_amount=240.0,
        rationale="Pulled back toward support.",
        created_at=_dt(),
    )


def _dt() -> datetime:
    return datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
```

- [ ] **Step 2: Run lifecycle tests to verify they fail**

Run:

```bash
uv run pytest -q tests/swing_spy/test_trade_lifecycle.py
```

Expected: fail with `ModuleNotFoundError: No module named 'swing_spy.trade_lifecycle'`.

- [ ] **Step 3: Implement lifecycle service**

Create `src/swing_spy/trade_lifecycle.py`:

```python
"""Business service for dashboard candidate and position lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from swing_spy.trade_models import (
    CandidateSnapshot,
    ClosePositionInput,
    ClosedTrade,
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
        self.store.skip_candidate(candidate_id, self.clock() + timedelta(days=_SKIP_DAYS))

    def execute_candidate(
        self, candidate_id: int, execution: ExecutionInput
    ) -> OpenPosition:
        """Create an open position from a user-confirmed external broker fill."""
        return self.store.create_open_position(candidate_id, execution)

    def list_open_positions(self, price_lookup: PriceLookup) -> list[MonitoredPosition]:
        """Return open positions with advisory monitoring state."""
        positions = self.store.list_open_positions()
        return [self._monitor(position, price_lookup(position.ticker)) for position in positions]

    def close_position(
        self, position_id: int, close_input: ClosePositionInput
    ) -> ClosedTrade:
        """Close a position after the user confirms the external broker sale."""
        return self.store.close_position(position_id, close_input)

    def _monitor(self, position: OpenPosition, current_price: float | None) -> MonitoredPosition:
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
    position: OpenPosition, current_price: float | None, days_held: int
) -> PositionStatus:
    if current_price is not None and current_price <= position.stop:
        return "STOP_REACHED"
    if current_price is not None and current_price >= position.target:
        return "TARGET_REACHED"
    if days_held >= _MAX_HOLDING_DAYS:
        return "DEADLINE_REACHED"
    return "OPEN"
```

- [ ] **Step 4: Run lifecycle tests to verify they pass**

Run:

```bash
uv run pytest -q tests/swing_spy/test_trade_lifecycle.py
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/swing_spy/trade_lifecycle.py tests/swing_spy/test_trade_lifecycle.py
git commit -m "Add dashboard lifecycle service"
```

## Task 4: Position Pricing Adapter

**Files:**
- Create: `src/swing_spy/position_pricing.py`
- Create: `tests/swing_spy/test_position_pricing.py`

- [ ] **Step 1: Write failing pricing tests**

Create `tests/swing_spy/test_position_pricing.py`:

```python
"""Tests for open-position price lookup."""

from __future__ import annotations

import pandas as pd

from swing_spy.position_pricing import PositionPricer


def test_price_lookup_returns_latest_quote_price() -> None:
    pricer = PositionPricer(download_history=lambda tickers: {"AAA": _frame([99.0, 101.5])})

    assert pricer.current_price("AAA") == 101.5


def test_price_lookup_returns_none_when_quote_missing() -> None:
    pricer = PositionPricer(download_history=lambda tickers: {})

    assert pricer.current_price("AAA") is None


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes})
```

- [ ] **Step 2: Run pricing tests to verify they fail**

Run:

```bash
uv run pytest -q tests/swing_spy/test_position_pricing.py
```

Expected: fail with `ModuleNotFoundError: No module named 'swing_spy.position_pricing'`.

- [ ] **Step 3: Implement pricing adapter**

Create `src/swing_spy/position_pricing.py`:

```python
"""Price lookup adapter for monitored dashboard positions."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from swing_spy.history import download_history as default_download_history
from swing_spy.history import quote_from_frame

DownloadFn = Callable[[list[str]], dict[str, pd.DataFrame]]


class PositionPricer:
    """Fetch current prices for open positions through the existing history provider."""

    def __init__(self, *, download_history: DownloadFn = default_download_history) -> None:
        self._download_history = download_history

    def current_price(self, ticker: str) -> float | None:
        """Return the latest available price for ``ticker``, or ``None`` if unavailable."""
        frames = self._download_history([ticker])
        frame = frames.get(ticker)
        if frame is None:
            return None
        quote = quote_from_frame(ticker, frame)
        return None if quote is None else quote.price
```

- [ ] **Step 4: Run pricing tests to verify they pass**

Run:

```bash
uv run pytest -q tests/swing_spy/test_position_pricing.py
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/swing_spy/position_pricing.py tests/swing_spy/test_position_pricing.py
git commit -m "Add dashboard position pricing"
```

## Task 5: Scanner Candidate Persistence

**Files:**
- Create: `src/swing_spy/dashboard_candidates.py`
- Create: `tests/swing_spy/test_dashboard_candidates.py`
- Modify: `src/swing_spy/scanner.py`
- Modify: `tests/swing_spy/test_swing_scanner.py`

- [ ] **Step 1: Write failing candidate conversion tests**

Create `tests/swing_spy/test_dashboard_candidates.py`:

```python
"""Tests for converting scanner candidates into dashboard snapshots."""

from __future__ import annotations

from datetime import UTC, date, datetime

from spy_core.models import Quote, Technicals
from swing_spy.dashboard_candidates import candidate_to_snapshot
from swing_spy.models import EarningsInfo, SwingNote, SwingSetup, TradePlan
from swing_spy.report import Candidate


def test_candidate_to_snapshot_preserves_trade_plan() -> None:
    snapshot = candidate_to_snapshot(_candidate())

    assert snapshot.ticker == "MUV2.DE"
    assert snapshot.entry == 468.0
    assert snapshot.stop == 458.0
    assert snapshot.target == 492.0
    assert snapshot.risk_reward == 2.4
    assert snapshot.earnings_warning == "Earnings in 3 day(s) on 2026-05-31."


def _candidate() -> Candidate:
    return Candidate(
        quote=Quote(
            ticker="MUV2.DE",
            price=468.0,
            previous_close=465.0,
            currency="EUR",
            as_of=datetime(2026, 5, 28, tzinfo=UTC),
        ),
        technicals=Technicals(last_close=468.0),
        setup=SwingSetup(
            is_setup=True,
            kind="pullback",
            entry_low=461.0,
            entry_high=468.0,
            stop=458.0,
            target_1=492.0,
            target_2=508.0,
            risk_reward=2.4,
            rationale="Pulled back toward support.",
        ),
        plan=TradePlan(
            shares=10,
            entry=468.0,
            stop=458.0,
            target=492.0,
            cost=4680.0,
            risk_amount=100.0,
            reward_amount=240.0,
            risk_reward=2.4,
            pct_of_account=46.8,
        ),
        note=SwingNote(rationale="Looks plausible.", news_sentiment_score=60.0, conviction=0.6),
        earnings=EarningsInfo(next_date=date(2026, 5, 31), days_until=3),
    )
```

- [ ] **Step 2: Add scanner recording test**

Modify `tests/swing_spy/test_swing_scanner.py` by adding:

```python
async def test_new_setup_records_dashboard_candidate(store: Store) -> None:
    sender = _Recorder()
    recorded = []
    scanner = _make_scanner(store, technicals=_PULLBACK, sender=sender)
    scanner.record_dashboard_candidate = recorded.append

    sent = await scanner.run_cycle()

    assert sent == 1
    assert len(recorded) == 1
    assert recorded[0].quote.ticker == "AAA"
```

- [ ] **Step 3: Run candidate tests to verify they fail**

Run:

```bash
uv run pytest -q tests/swing_spy/test_dashboard_candidates.py tests/swing_spy/test_swing_scanner.py::test_new_setup_records_dashboard_candidate
```

Expected: fail because `swing_spy.dashboard_candidates` and scanner recording do not exist.

- [ ] **Step 4: Implement candidate conversion**

Create `src/swing_spy/dashboard_candidates.py`:

```python
"""Convert scanner candidates into persisted dashboard snapshots."""

from __future__ import annotations

from swing_spy.report import Candidate
from swing_spy.trade_models import CandidateSnapshot


def candidate_to_snapshot(candidate: Candidate) -> CandidateSnapshot:
    """Return a dashboard snapshot from a fully built scanner candidate."""
    earnings_warning = None
    if candidate.earnings.is_imminent:
        next_date = "unknown" if candidate.earnings.next_date is None else candidate.earnings.next_date.isoformat()
        earnings_warning = f"Earnings in {candidate.earnings.days_until} day(s) on {next_date}."
    return CandidateSnapshot(
        ticker=candidate.quote.ticker,
        signature=candidate.signature(),
        setup_kind=candidate.setup.kind,
        currency=candidate.quote.currency,
        entry=candidate.plan.entry,
        stop=candidate.plan.stop,
        target=candidate.plan.target,
        risk_reward=candidate.plan.risk_reward,
        shares=candidate.plan.shares,
        cost=candidate.plan.cost,
        risk_amount=candidate.plan.risk_amount,
        reward_amount=candidate.plan.reward_amount,
        rationale=candidate.setup.rationale,
        earnings_warning=earnings_warning,
        created_at=candidate.quote.as_of,
    )
```

- [ ] **Step 5: Modify scanner to expose a dashboard recorder**

Modify `src/swing_spy/scanner.py`:

```python
from collections.abc import Awaitable, Callable

DashboardRecordFn = Callable[[Candidate], None]
```

Add constructor parameter:

```python
        record_dashboard_candidate: DashboardRecordFn | None = None,
```

Assign:

```python
        self.record_dashboard_candidate = record_dashboard_candidate
```

In `_alert`, after `candidate = await self.build_candidate(s)` and before sending:

```python
        if self.record_dashboard_candidate is not None:
            self.record_dashboard_candidate(candidate)
```

Use a public attribute name so tests and the scheduler can inject persistence without depending
on Streamlit.

- [ ] **Step 6: Run candidate/scanner tests to verify they pass**

Run:

```bash
uv run pytest -q tests/swing_spy/test_dashboard_candidates.py tests/swing_spy/test_swing_scanner.py
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/swing_spy/dashboard_candidates.py src/swing_spy/scanner.py tests/swing_spy/test_dashboard_candidates.py tests/swing_spy/test_swing_scanner.py
git commit -m "Persist scanner candidates for dashboard"
```

## Task 6: Wire Candidate Persistence Into Scheduler

**Files:**
- Modify: `src/swing_spy/scheduler.py`
- Create: `tests/swing_spy/test_dashboard_scheduler.py`

- [ ] **Step 1: Inspect scanner construction**

Run:

```bash
sed -n '1,260p' src/swing_spy/scheduler.py
```

Expected: locate the helper that builds `Scanner` for `run_once`, `run_forever`, and `run_check`.

- [ ] **Step 2: Write failing scheduler integration test**

Create `tests/swing_spy/test_dashboard_scheduler.py` with a focused test for the scanner factory
or setup helper found in Step 1. The assertion must prove that the scanner receives a
`record_dashboard_candidate` callback that writes through `TradeLifecycleService`.

Use this exact test:

```python
"""Tests for dashboard candidate persistence wiring."""

from __future__ import annotations

from pathlib import Path

from swing_spy.config import Secrets
from swing_spy.models import SwingConfig
from swing_spy.scheduler import build_scanner


async def test_build_scanner_wires_dashboard_candidate_recorder(tmp_path: Path) -> None:
    config = SwingConfig(db_path=str(tmp_path / "swing.sqlite3"))
    secrets = Secrets(
        telegram_bot_token="T",
        telegram_chat_id="C",
        gemini_api_key="G",
    )

    async with build_scanner(config, secrets) as scanner:
        assert scanner.record_dashboard_candidate is not None
```

- [ ] **Step 3: Run scheduler test to verify it fails**

Run:

```bash
uv run pytest -q tests/swing_spy/test_dashboard_scheduler.py
```

Expected: fail because the factory does not expose dashboard recorder wiring yet.

- [ ] **Step 4: Implement scheduler wiring**

Modify `src/swing_spy/scheduler.py` to create one `TradeStore` and `TradeLifecycleService` for
the configured `db_path`, then pass a recorder into `Scanner`:

```python
from swing_spy.dashboard_candidates import candidate_to_snapshot
from swing_spy.report import Candidate
from swing_spy.trade_lifecycle import TradeLifecycleService
from swing_spy.trade_store import TradeStore
```

Modify the existing `build_scanner` async context manager:

```python
@asynccontextmanager
async def build_scanner(config: SwingConfig, secrets: Secrets) -> AsyncIterator[Scanner]:
    """Construct a wired scanner, cleaning up stores and HTTP client on exit."""
    store = Store(config.db_path)
    trade_store = TradeStore(config.db_path)
    trade_service = TradeLifecycleService(trade_store)

    def record_dashboard_candidate(candidate: Candidate) -> None:
        trade_service.record_candidate(candidate_to_snapshot(candidate))

    try:
        agent = build_agent(secrets.gemini_api_key, config.gemini_model)
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            yield Scanner(
                config,
                store,
                agent,
                client,
                telegram_token=secrets.telegram_bot_token,
                telegram_chat_id=secrets.telegram_chat_id,
                record_dashboard_candidate=record_dashboard_candidate,
            )
    finally:
        trade_store.close()
        store.close()
```

Modify `run_check` so one-off checks also persist a dashboard candidate before sending:

```python
        candidate = await scanner.build_candidate(evaluated)
        if scanner.record_dashboard_candidate is not None:
            scanner.record_dashboard_candidate(candidate)
        return await scanner.send_candidate(candidate)
```

- [ ] **Step 5: Run scheduler test to verify it passes**

Run:

```bash
uv run pytest -q tests/swing_spy/test_dashboard_scheduler.py
```

Expected: pass.

- [ ] **Step 6: Run scanner tests**

Run:

```bash
uv run pytest -q tests/swing_spy/test_swing_scanner.py tests/swing_spy/test_dashboard_scheduler.py
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/swing_spy/scheduler.py tests/swing_spy/test_dashboard_scheduler.py
git commit -m "Wire dashboard candidates into scanner"
```

## Task 7: Streamlit Dependency And Boundary Test

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/swing_spy/test_streamlit_boundary.py`

- [ ] **Step 1: Add boundary test**

Create `tests/swing_spy/test_streamlit_boundary.py`:

```python
"""Tests that keep Streamlit isolated from reusable services."""

from __future__ import annotations

from pathlib import Path


def test_non_ui_modules_do_not_import_streamlit() -> None:
    src = Path("src/swing_spy")
    offenders = []
    for path in src.glob("*.py"):
        if path.name.startswith("__"):
            continue
        text = path.read_text()
        if "streamlit" in text:
            offenders.append(str(path))

    assert offenders == []
```

- [ ] **Step 2: Add Streamlit dependency**

Run:

```bash
uv add 'streamlit==1.57.0'
```

Expected: `pyproject.toml` includes `streamlit==1.57.0` and `uv.lock` is updated.

- [ ] **Step 3: Run boundary test**

Run:

```bash
uv run pytest -q tests/swing_spy/test_streamlit_boundary.py
```

Expected: pass.

- [ ] **Step 4: Run dependency import check**

Run:

```bash
uv run python -c "import streamlit; print(streamlit.__version__)"
```

Expected: `1.57.0`.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml uv.lock tests/swing_spy/test_streamlit_boundary.py
git commit -m "Add Streamlit dashboard dependency"
```

## Task 8: Streamlit UI Package

**Files:**
- Create: `src/swing_spy/streamlit_app/__init__.py`
- Create: `src/swing_spy/streamlit_app/service_factory.py`
- Create: `src/swing_spy/streamlit_app/components.py`
- Create: `src/swing_spy/streamlit_app/app.py`
- Create: `tests/swing_spy/test_streamlit_app.py`

- [ ] **Step 1: Write UI import smoke test**

Create `tests/swing_spy/test_streamlit_app.py`:

```python
"""Smoke tests for Streamlit UI package boundaries."""

from __future__ import annotations


def test_streamlit_app_modules_import() -> None:
    from swing_spy.streamlit_app import app, components, service_factory

    assert app is not None
    assert components is not None
    assert service_factory is not None
```

- [ ] **Step 2: Run UI smoke test to verify it fails**

Run:

```bash
uv run pytest -q tests/swing_spy/test_streamlit_app.py
```

Expected: fail because `swing_spy.streamlit_app` does not exist.

- [ ] **Step 3: Create Streamlit package marker**

Create `src/swing_spy/streamlit_app/__init__.py`:

```python
"""Streamlit-only UI package for the swing dashboard."""
```

- [ ] **Step 4: Create service factory**

Create `src/swing_spy/streamlit_app/service_factory.py`:

```python
"""Streamlit-only service construction for the dashboard UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from swing_spy.config import DEFAULT_CONFIG_PATH, load_config
from swing_spy.position_pricing import PositionPricer
from swing_spy.trade_lifecycle import TradeLifecycleService
from swing_spy.trade_store import TradeStore


@st.cache_resource
def get_lifecycle_service(config_path: str = str(DEFAULT_CONFIG_PATH)) -> TradeLifecycleService:
    """Return a cached lifecycle service for the configured dashboard database."""
    config = load_config(Path(config_path))
    return TradeLifecycleService(TradeStore(config.db_path))


@st.cache_resource
def get_position_pricer() -> PositionPricer:
    """Return a cached price adapter for monitored positions."""
    return PositionPricer()
```

- [ ] **Step 5: Create UI components**

Create `src/swing_spy/streamlit_app/components.py`:

```python
"""Reusable Streamlit components for the swing dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from swing_spy.trade_models import (
    CandidateSnapshot,
    ClosePositionInput,
    ExecutionInput,
    MonitoredPosition,
)


def render_candidate_card(candidate: CandidateSnapshot) -> None:
    """Render one candidate decision card."""
    st.subheader(candidate.ticker)
    st.caption(f"{candidate.setup_kind} · {candidate.currency}")
    cols = st.columns(4)
    cols[0].metric("Entry", f"{candidate.entry:.2f}")
    cols[1].metric("Stop", f"{candidate.stop:.2f}")
    cols[2].metric("Target", f"{candidate.target:.2f}")
    cols[3].metric("R:R", f"{candidate.risk_reward:g}")
    st.write(f"Shares: **{candidate.shares}** · Risk: **{candidate.risk_amount:,.2f}**")
    if candidate.earnings_warning is not None:
        st.warning(candidate.earnings_warning)
    st.write(candidate.rationale)


def execution_form(candidate: CandidateSnapshot) -> ExecutionInput | None:
    """Render execution confirmation form and return input after submit."""
    with st.form(f"execute-{candidate.id}"):
        actual_entry = st.number_input("Actual entry", value=float(candidate.entry), min_value=0.01)
        shares = st.number_input("Shares", value=int(candidate.shares), min_value=1, step=1)
        note = st.text_input("Note", value="")
        submitted = st.form_submit_button("Confirm execution")
    if not submitted:
        return None
    return ExecutionInput(
        actual_entry=actual_entry,
        shares=int(shares),
        executed_at=datetime.now(UTC),
        note=note,
    )


def render_position_card(monitored: MonitoredPosition) -> None:
    """Render one monitored open position card."""
    position = monitored.position
    st.subheader(position.ticker)
    st.caption(f"{monitored.status} · {position.currency} · day {monitored.days_held}")
    cols = st.columns(4)
    cols[0].metric("Entry", f"{position.actual_entry:.2f}")
    cols[1].metric("Current", _money(monitored.current_price))
    cols[2].metric("Stop", f"{position.stop:.2f}")
    cols[3].metric("Target", f"{position.target:.2f}")
    st.metric("Unrealized P/L", _money(monitored.unrealized_pnl))


def close_form(monitored: MonitoredPosition) -> ClosePositionInput | None:
    """Render close confirmation form and return input after submit."""
    position = monitored.position
    default_exit = monitored.current_price or position.target
    if monitored.status == "STOP_REACHED":
        default_exit = position.stop
    if monitored.status == "TARGET_REACHED":
        default_exit = position.target
    with st.form(f"close-{position.id}"):
        exit_price = st.number_input("Exit price", value=float(default_exit), min_value=0.01)
        shares = st.number_input("Shares sold", value=int(position.shares), min_value=1, step=1)
        exit_reason = st.selectbox("Exit reason", ["TARGET", "STOP", "DEADLINE", "MANUAL"])
        note = st.text_input("Exit note", value="")
        submitted = st.form_submit_button("Confirm sale")
    if not submitted:
        return None
    return ClosePositionInput(
        exit_price=exit_price,
        shares=int(shares),
        exited_at=datetime.now(UTC),
        exit_reason=exit_reason,
        note=note,
    )


def _money(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:,.2f}"
```

- [ ] **Step 6: Create Streamlit entrypoint**

Create `src/swing_spy/streamlit_app/app.py`:

```python
"""Streamlit entrypoint for the swing dashboard."""

from __future__ import annotations

import streamlit as st

from swing_spy.streamlit_app.components import (
    close_form,
    execution_form,
    render_candidate_card,
    render_position_card,
)
from swing_spy.streamlit_app.service_factory import get_lifecycle_service, get_position_pricer


def main() -> None:
    """Render the dashboard."""
    st.set_page_config(page_title="Swing Dashboard", layout="wide")
    st.title("Swing Dashboard")

    service = get_lifecycle_service()
    pricer = get_position_pricer()

    tab_candidates, tab_positions = st.tabs(["Potential Swing Trades", "Open Positions"])
    with tab_candidates:
        _render_candidates(service)
    with tab_positions:
        _render_positions(service, pricer)


def _render_candidates(service: object) -> None:
    candidates = service.list_candidates()
    if not candidates:
        st.info("No active swing candidates. Run `uv run swing-spy scan --once` to refresh.")
        return
    for row in _chunks(candidates, 4):
        cols = st.columns(len(row))
        for col, candidate in zip(cols, row, strict=True):
            with col.container(border=True):
                render_candidate_card(candidate)
                left, right = st.columns(2)
                if left.button("Executed", key=f"execute-open-{candidate.id}"):
                    st.session_state["execute_candidate_id"] = candidate.id
                if right.button("Skip 1d", key=f"skip-{candidate.id}"):
                    service.skip_candidate(candidate.id)
                    st.rerun()
                if st.session_state.get("execute_candidate_id") == candidate.id:
                    execution = execution_form(candidate)
                    if execution is not None:
                        service.execute_candidate(candidate.id, execution)
                        st.session_state.pop("execute_candidate_id", None)
                        st.rerun()


def _render_positions(service: object, pricer: object) -> None:
    positions = service.list_open_positions(pricer.current_price)
    if not positions:
        st.info("No open positions.")
        return
    for row in _chunks(positions, 3):
        cols = st.columns(len(row))
        for col, monitored in zip(cols, row, strict=True):
            position = monitored.position
            with col.container(border=True):
                render_position_card(monitored)
                if st.button("Sold", key=f"sold-open-{position.id}"):
                    st.session_state["close_position_id"] = position.id
                if st.session_state.get("close_position_id") == position.id:
                    close_input = close_form(monitored)
                    if close_input is not None:
                        service.close_position(position.id, close_input)
                        st.session_state.pop("close_position_id", None)
                        st.rerun()


def _chunks[T](items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run UI smoke and boundary tests**

Run:

```bash
uv run pytest -q tests/swing_spy/test_streamlit_app.py tests/swing_spy/test_streamlit_boundary.py
```

Expected: pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add src/swing_spy/streamlit_app tests/swing_spy/test_streamlit_app.py
git commit -m "Add Streamlit dashboard UI"
```

## Task 9: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add dashboard run instructions**

Modify `README.md` under the `Run` section by adding:

```markdown
# Swing dashboard
uv run swing-spy scan --once
uv run streamlit run src/swing_spy/streamlit_app/app.py
```

Add one sentence: "Run a scan first so the dashboard has persisted candidate snapshots to show."

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest -q tests/swing_spy
```

Expected: pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check .
```

Expected: pass with no warnings.

- [ ] **Step 4: Run type check**

Run:

```bash
uv run ty check
```

Expected: pass with no errors.

- [ ] **Step 5: Launch dashboard manually**

Run:

```bash
uv run streamlit run src/swing_spy/streamlit_app/app.py
```

Expected: Streamlit prints a local URL. Open it and verify the app shows tabs for
`Potential Swing Trades` and `Open Positions`. If the database has no candidates, the candidates
tab shows the scan instruction message.

- [ ] **Step 6: Commit docs**

Run:

```bash
git add README.md
git commit -m "Document swing dashboard usage"
```

## Self-Review Notes

- Spec coverage:
  - Candidate cards: Tasks 5 and 8.
  - Execute and skip actions: Tasks 2, 3, and 8.
  - Open position monitoring: Tasks 3, 4, and 8.
  - Human-in-the-loop close: Tasks 2, 3, and 8.
  - Streamlit isolation: Tasks 7 and 8.
  - Future FastAPI/React reuse: service modules in Tasks 1-4 with no Streamlit imports.
- Placeholder scan:
  - No unresolved placeholders or vague validation steps remain.
- Type consistency:
  - `CandidateSnapshot`, `ExecutionInput`, `OpenPosition`, `MonitoredPosition`,
    `ClosePositionInput`, and `ClosedTrade` are defined before use.
  - Service methods match the spec examples: `execute_candidate`, `close_position`,
    `list_open_positions`.
