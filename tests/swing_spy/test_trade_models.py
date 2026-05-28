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
