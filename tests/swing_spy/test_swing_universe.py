"""Tests for universe resolution and symbol conventions."""

from __future__ import annotations

import pytest

from swing_spy.models import SwingConfig, UniverseConfig
from swing_spy.universe import DAX40, SP500, currency_for, get_universe


def test_default_universe_merges_both_indexes() -> None:
    tickers = get_universe(SwingConfig())
    assert "MUV2.DE" in tickers  # the Munich Re example, a DAX name
    assert "AAPL" in tickers
    assert len(tickers) == len(set(DAX40) | set(SP500))


def test_single_index_and_extras() -> None:
    config = UniverseConfig(indexes=["DAX40"], extra_tickers=["FOO.XY"])
    tickers = get_universe(config)
    assert "FOO.XY" in tickers
    assert "AAPL" not in tickers  # S&P not selected
    assert "SAP.DE" in tickers


def test_unknown_index_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown index"):
        get_universe(UniverseConfig(indexes=["NASDAQ100"]))


def test_symbols_use_yahoo_conventions() -> None:
    assert "BRK-B" in SP500 and "BRK.B" not in SP500  # share class uses a dash
    assert all(s.endswith(".DE") or "." in s for s in DAX40)  # German listings carry a suffix


def test_currency_inference_from_suffix() -> None:
    assert currency_for("MUV2.DE") == "EUR"
    assert currency_for("AIR.PA") == "EUR"
    assert currency_for("AAPL") == "USD"
    assert currency_for("VOD.L") == "GBP"
