"""Tests for fundamentals mapping from yfinance ``.info``."""

from __future__ import annotations

from typing import Any

from signal_spy.providers.fundamentals import get_fundamentals


class _FakeTicker:
    def __init__(self, info: dict[str, Any]) -> None:
        self._info = info

    @property
    def info(self) -> dict[str, Any]:
        return self._info


def _factory(info: dict[str, Any]):
    return lambda _ticker: _FakeTicker(info)


def test_maps_known_fields() -> None:
    info = {
        "trailingPE": 37.4,
        "profitMargins": 0.27,
        "marketCap": 4_500_000_000_000,
        "targetMeanPrice": 308.6,
        "recommendationKey": "buy",
        "numberOfAnalystOpinions": 43,
    }

    f = get_fundamentals("AAPL", ticker_factory=_factory(info))

    assert f.trailing_pe == 37.4
    assert f.profit_margin == 0.27
    assert f.market_cap == 4_500_000_000_000
    assert f.target_mean_price == 308.6
    assert f.recommendation_key == "buy"
    assert f.num_analysts == 43


def test_missing_fields_become_none() -> None:
    f = get_fundamentals("XYZ", ticker_factory=_factory({"trailingPE": 12.0}))

    assert f.trailing_pe == 12.0
    assert f.forward_pe is None
    assert f.recommendation_key is None
    assert f.num_analysts is None


def test_malformed_values_do_not_raise() -> None:
    info = {"trailingPE": "n/a", "numberOfAnalystOpinions": None, "recommendationKey": "  "}

    f = get_fundamentals("XYZ", ticker_factory=_factory(info))

    assert f.trailing_pe is None
    assert f.num_analysts is None
    assert f.recommendation_key is None


def test_empty_info_yields_all_none() -> None:
    f = get_fundamentals("XYZ", ticker_factory=_factory({}))

    assert f.market_cap is None
    assert f.beta is None
