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
