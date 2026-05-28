"""Reusable Streamlit components for the swing dashboard."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import streamlit as st

from swing_spy.trade_models import (
    CandidateSnapshot,
    ClosePositionInput,
    ExecutionInput,
    ExitReason,
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
        exit_reason=cast("ExitReason", exit_reason),
        note=note,
    )


def _money(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:,.2f}"
