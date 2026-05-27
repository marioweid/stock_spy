"""Bulk price history for the universe, and deriving a quote from a history frame.

Scanning hundreds of tickers one HTTP call at a time is slow, so the scanner pulls daily
history for the whole universe in a few batched ``yf.download`` calls, then reuses
``spy_core``'s pure indicator math on the in-memory frames. The quote, too, is read straight
from the frame, avoiding a second round of per-ticker network calls.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from spy_core.models import Quote
from swing_spy.universe import currency_for

logger = logging.getLogger(__name__)

_CHUNK = 100


def download_history(tickers: list[str], *, period: str = "1y") -> dict[str, pd.DataFrame]:
    """Download daily OHLCV history for many tickers, returned as one frame per ticker.

    Args:
        tickers: Yahoo symbols to fetch.
        period: History window passed to yfinance (default one year).

    Returns:
        A mapping of ticker to its OHLCV DataFrame; tickers with no data are omitted.
    """
    frames: dict[str, pd.DataFrame] = {}
    for start in range(0, len(tickers), _CHUNK):
        chunk = tickers[start : start + _CHUNK]
        raw = yf.download(
            chunk,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        frames.update(_split_frames(raw, chunk))
    return frames


def _split_frames(raw: Any, chunk: list[str]) -> dict[str, pd.DataFrame]:
    """Split a (possibly multi-ticker) yfinance download into a per-ticker mapping."""
    if raw is None or len(raw) == 0:
        return {}
    out: dict[str, pd.DataFrame] = {}
    multi = isinstance(raw.columns, pd.MultiIndex)
    for ticker in chunk:
        frame = raw[ticker] if multi and ticker in raw.columns.get_level_values(0) else raw
        if not multi and len(chunk) > 1:
            continue
        if "Close" in frame.columns and frame["Close"].dropna().shape[0] > 0:
            out[ticker] = frame
    return out


def quote_from_frame(ticker: str, frame: pd.DataFrame) -> Quote | None:
    """Build a :class:`Quote` from the last two closing prices in a history frame.

    Returns ``None`` when the frame lacks at least two finite closes to compare.
    """
    closes = frame["Close"].dropna()
    if len(closes) < 2:
        return None
    price = float(closes.iloc[-1])
    previous_close = float(closes.iloc[-2])
    if not (math.isfinite(price) and math.isfinite(previous_close)) or previous_close == 0:
        return None
    return Quote(
        ticker=ticker,
        price=price,
        previous_close=previous_close,
        currency=currency_for(ticker),
        as_of=datetime.now(UTC),
    )
