"""Tests for technical indicators computed from a price frame."""

from __future__ import annotations

import pandas as pd

from spy_core.providers.technicals import get_technicals


def _frame(closes: list[float]) -> pd.DataFrame:
    """Build an OHLCV frame from a list of closes (High = close+1, Low = close-1)."""
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 1 for c in closes],
            "Low": [c - 1 for c in closes],
            "Close": closes,
            "Volume": [1_000] * len(closes),
        }
    )


def _get(closes: list[float]):
    return get_technicals("T", history_fn=lambda _t: _frame(closes))


def test_constant_series_indicators() -> None:
    t = _get([100.0] * 60)

    assert t.last_close == 100.0
    assert t.sma_50 == 100.0
    assert t.sma_200 is None  # not enough history
    assert t.atr_14 == 2.0  # high-low band is always 2
    assert t.support == 99.0
    assert t.resistance == 101.0
    assert t.volatility_30d == 0.0
    assert t.pct_from_52w_high == 0.0


def test_rising_series_rsi_is_max() -> None:
    t = _get([100.0 + i for i in range(30)])

    assert t.rsi_14 == 100.0  # only gains, no losses


def test_macd_zero_for_flat_series() -> None:
    t = _get([50.0] * 40)

    assert t.macd is not None
    assert abs(t.macd) < 1e-9
    assert t.macd_signal is not None


def test_short_history_yields_none_indicators() -> None:
    t = _get([100.0] * 10)

    assert t.last_close == 100.0
    assert t.sma_50 is None
    assert t.rsi_14 is None
    assert t.macd is None
    assert t.atr_14 is None
    assert t.support == 99.0  # levels still computable with >=2 bars


def test_empty_history_yields_blank_technicals() -> None:
    t = get_technicals("T", history_fn=lambda _t: _frame([]))

    assert t.last_close is None
    assert t.sma_50 is None
