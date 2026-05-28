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
