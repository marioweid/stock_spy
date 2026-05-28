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
