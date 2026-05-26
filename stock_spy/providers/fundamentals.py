"""Company fundamentals via the yfinance ``.info`` mapping."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import yfinance as yf

from stock_spy.models import Fundamentals

_FLOAT_FIELDS: dict[str, str] = {
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "price_to_book": "priceToBook",
    "peg_ratio": "pegRatio",
    "profit_margin": "profitMargins",
    "gross_margin": "grossMargins",
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
    "return_on_equity": "returnOnEquity",
    "debt_to_equity": "debtToEquity",
    "beta": "beta",
    "market_cap": "marketCap",
    "target_mean_price": "targetMeanPrice",
    "target_high_price": "targetHighPrice",
    "target_low_price": "targetLowPrice",
    "fifty_two_week_high": "fiftyTwoWeekHigh",
    "fifty_two_week_low": "fiftyTwoWeekLow",
    "dividend_yield": "dividendYield",
    "free_cashflow": "freeCashflow",
    "total_revenue": "totalRevenue",
}


class _TickerLike(Protocol):
    @property
    def info(self) -> Any: ...


def get_fundamentals(
    ticker: str,
    *,
    ticker_factory: Callable[[str], _TickerLike] = yf.Ticker,
) -> Fundamentals:
    """Fetch company fundamentals for a ticker.

    A single missing or malformed metric yields ``None`` for that field rather than raising,
    so a partial profile never aborts a report.

    Args:
        ticker: The ticker symbol.
        ticker_factory: Builds the yfinance ticker object; injectable for tests.

    Returns:
        A :class:`Fundamentals` with ``None`` for any unavailable field.
    """
    info = ticker_factory(ticker).info or {}
    values: dict[str, Any] = {
        field: _as_float(info.get(key)) for field, key in _FLOAT_FIELDS.items()
    }
    values["recommendation_key"] = _as_str(info.get("recommendationKey"))
    values["num_analysts"] = _as_int(info.get("numberOfAnalystOpinions"))
    return Fundamentals(**values)


def _as_float(value: Any) -> float | None:
    """Coerce a value to ``float``, or ``None`` if absent or not numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Coerce a value to ``int``, or ``None`` if absent or not numeric."""
    number = _as_float(value)
    return None if number is None else int(number)


def _as_str(value: Any) -> str | None:
    """Coerce a value to a non-empty ``str``, or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
