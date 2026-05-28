"""Price lookup adapter for monitored dashboard positions."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from swing_spy.history import download_history as default_download_history
from swing_spy.history import quote_from_frame

DownloadFn = Callable[[list[str]], dict[str, pd.DataFrame]]


class PositionPricer:
    """Fetch current prices for open positions through the existing history provider."""

    def __init__(self, *, download_history: DownloadFn = default_download_history) -> None:
        self._download_history = download_history

    def current_price(self, ticker: str) -> float | None:
        """Return the latest available price for ``ticker``, or ``None`` if unavailable."""
        frames = self._download_history([ticker])
        frame = frames.get(ticker)
        if frame is None:
            return None
        quote = quote_from_frame(ticker, frame)
        return None if quote is None else quote.price
