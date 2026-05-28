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
    service.execute_candidate(
        candidate_id,
        ExecutionInput(actual_entry=468.0, shares=10, executed_at=_dt()),
    )

    monitored = service.list_open_positions(lambda _ticker: 457.0)

    assert monitored[0].status == "STOP_REACHED"
    assert service.store.list_closed_trades() == []
    assert len(service.store.list_open_positions()) == 1
    service.close()


def test_target_and_deadline_states_are_reported() -> None:
    service = _service()
    candidate_id = service.record_candidate(_candidate())
    service.execute_candidate(
        candidate_id,
        ExecutionInput(actual_entry=468.0, shares=10, executed_at=_dt()),
    )

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
