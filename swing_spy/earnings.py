"""Next-earnings lookup, so the scanner can warn about holding a swing trade through earnings."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import yfinance as yf

from swing_spy.models import EarningsInfo

logger = logging.getLogger(__name__)


def get_earnings(
    ticker: str,
    *,
    calendar_fn: Callable[[str], Any] = lambda t: yf.Ticker(t).calendar,
) -> EarningsInfo:
    """Return the next scheduled earnings date for a ticker and days until it.

    yfinance occasionally lacks or malforms this field; any failure degrades to an empty
    :class:`EarningsInfo` rather than aborting the scan.

    Args:
        ticker: The ticker symbol.
        calendar_fn: Returns yfinance's calendar object/dict; injectable for tests.
    """
    try:
        next_date = _extract_date(calendar_fn(ticker))
    except Exception:
        logger.debug("Earnings lookup failed for %s", ticker, exc_info=True)
        return EarningsInfo()
    if next_date is None:
        return EarningsInfo()
    days_until = (next_date - datetime.now(UTC).date()).days
    return EarningsInfo(next_date=next_date, days_until=days_until)


def _extract_date(calendar: Any) -> date | None:
    """Pull the soonest earnings date out of yfinance's calendar (dict or DataFrame)."""
    value: Any = None
    if isinstance(calendar, dict):
        value = calendar.get("Earnings Date")
    elif calendar is not None and "Earnings Date" in getattr(calendar, "index", []):
        value = calendar.loc["Earnings Date"].iloc[0]
    if isinstance(value, list | tuple):
        value = value[0] if value else None
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()
