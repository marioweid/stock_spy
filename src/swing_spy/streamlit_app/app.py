"""Streamlit entrypoint for the swing dashboard."""

from __future__ import annotations

import streamlit as st

from swing_spy.position_pricing import PositionPricer
from swing_spy.streamlit_app.components import (
    close_form,
    execution_form,
    render_candidate_card,
    render_position_card,
)
from swing_spy.streamlit_app.service_factory import (
    get_lifecycle_service,
    get_position_pricer,
)
from swing_spy.trade_lifecycle import TradeLifecycleService


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


def _render_candidates(service: TradeLifecycleService) -> None:
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
                    service.skip_candidate(_require_id(candidate.id))
                    st.rerun()
                if st.session_state.get("execute_candidate_id") == candidate.id:
                    execution = execution_form(candidate)
                    if execution is not None:
                        service.execute_candidate(_require_id(candidate.id), execution)
                        st.session_state.pop("execute_candidate_id", None)
                        st.rerun()


def _render_positions(service: TradeLifecycleService, pricer: PositionPricer) -> None:
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
                        service.close_position(_require_id(position.id), close_input)
                        st.session_state.pop("close_position_id", None)
                        st.rerun()


def _chunks[T](items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _require_id(value: int | None) -> int:
    if value is None:
        raise ValueError("Expected persisted dashboard object to have an id.")
    return value


if __name__ == "__main__":
    main()
