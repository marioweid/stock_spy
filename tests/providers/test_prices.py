"""Tests for the yfinance price provider."""

from __future__ import annotations

import pytest

from stock_spy.providers.prices import QuoteUnavailableError, get_quote


class _FakeFastInfo:
    def __init__(self, **fields: object) -> None:
        self._fields = fields

    def __getattr__(self, name: str) -> object:
        try:
            return self._fields[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _FakeTicker:
    def __init__(self, info: _FakeFastInfo) -> None:
        self.fast_info = info


def _factory(**fields: object):
    return lambda _ticker: _FakeTicker(_FakeFastInfo(**fields))


def test_get_quote_builds_quote_and_computes_change() -> None:
    quote = get_quote(
        "AAPL",
        ticker_factory=_factory(last_price=110.0, previous_close=100.0, currency="USD"),
    )

    assert quote.ticker == "AAPL"
    assert quote.price == 110.0
    assert quote.previous_close == 100.0
    assert quote.currency == "USD"
    assert quote.pct_change == pytest.approx(10.0)


def test_get_quote_defaults_currency_to_usd() -> None:
    quote = get_quote(
        "BRK-B",
        ticker_factory=_factory(last_price=400.0, previous_close=400.0, currency=None),
    )

    assert quote.currency == "USD"
    assert quote.pct_change == 0.0


def test_get_quote_raises_when_price_missing() -> None:
    with pytest.raises(QuoteUnavailableError, match="No price data"):
        get_quote(
            "FAKE",
            ticker_factory=_factory(last_price=None, previous_close=100.0),
        )


def test_get_quote_raises_when_previous_close_missing() -> None:
    with pytest.raises(QuoteUnavailableError):
        get_quote(
            "FAKE",
            ticker_factory=_factory(last_price=100.0, previous_close=None),
        )
