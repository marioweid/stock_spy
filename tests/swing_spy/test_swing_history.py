"""Tests for deriving a quote from a history frame."""

from __future__ import annotations

import pandas as pd

from swing_spy.history import quote_from_frame


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes})


def test_quote_uses_last_two_closes() -> None:
    quote = quote_from_frame("MUV2.DE", _frame([460.0, 465.0, 468.0]))
    assert quote is not None
    assert quote.price == 468.0
    assert quote.previous_close == 465.0
    assert quote.currency == "EUR"  # inferred from the .DE suffix
    assert round(quote.pct_change, 2) == round((468 - 465) / 465 * 100, 2)


def test_too_few_closes_yields_none() -> None:
    assert quote_from_frame("AAPL", _frame([100.0])) is None


def test_nan_closes_are_dropped_before_comparison() -> None:
    quote = quote_from_frame("AAPL", _frame([float("nan"), 100.0, 101.0]))
    assert quote is not None
    assert quote.price == 101.0
    assert quote.previous_close == 100.0
