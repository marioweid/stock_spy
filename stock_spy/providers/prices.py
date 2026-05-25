"""Price quotes via yfinance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

import yfinance as yf

from stock_spy.models import Quote


class QuoteUnavailableError(RuntimeError):
    """Raised when a usable quote cannot be obtained for a ticker."""


class _TickerLike(Protocol):
    @property
    def fast_info(self) -> Any: ...


def get_quote(
    ticker: str,
    *,
    ticker_factory: Callable[[str], _TickerLike] = yf.Ticker,
) -> Quote:
    """Fetch the latest price and previous close for a ticker.

    Args:
        ticker: The ticker symbol (e.g. ``"BRK-B"``).
        ticker_factory: Builds the yfinance ticker object; injectable for tests.

    Returns:
        A populated :class:`Quote`.

    Raises:
        QuoteUnavailableError: If price or previous close is missing.
    """
    info = ticker_factory(ticker).fast_info
    price = _read(info, "last_price")
    previous_close = _read(info, "previous_close")
    if price is None or previous_close is None:
        raise QuoteUnavailableError(
            f"No price data for {ticker!r} (last_price={price}, previous_close={previous_close}). "
            "Check the symbol is valid on Yahoo Finance."
        )
    currency = _read(info, "currency") or "USD"
    return Quote(
        ticker=ticker,
        price=float(price),
        previous_close=float(previous_close),
        currency=str(currency),
        as_of=datetime.now(UTC),
    )


def _read(info: Any, key: str) -> Any:
    """Read a field from yfinance fast_info via attribute or mapping access."""
    value = getattr(info, key, None)
    if value is None:
        try:
            value = info[key]
        except (KeyError, TypeError):
            value = None
    return value
