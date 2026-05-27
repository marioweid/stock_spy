"""Market-data primitives shared across the spy tools.

These are the raw, domain-agnostic readings (a price quote, a news headline, a set of technical
indicators). Domain models (portfolios, signals, swing setups) live in the leaf packages.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Quote(BaseModel):
    """A point-in-time price reading for a ticker."""

    ticker: str
    price: float
    previous_close: float
    currency: str
    as_of: datetime

    @property
    def pct_change(self) -> float:
        """Percent change from the previous close to the current price."""
        if self.previous_close == 0:
            return 0.0
        return (self.price - self.previous_close) / self.previous_close * 100.0


class NewsItem(BaseModel):
    """A single news headline for a ticker."""

    ticker: str
    title: str
    url: str
    summary: str = ""
    published: datetime | None = None
    guid: str

    def dedup_key(self) -> str:
        """Stable identifier used to avoid alerting on the same item twice."""
        return self.guid or self.url


class Technicals(BaseModel):
    """Indicators derived from price history; any field may be missing for short history."""

    last_close: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    atr_14: float | None = None
    support: float | None = None
    resistance: float | None = None
    recent_swing_low: float | None = None
    recent_swing_high: float | None = None
    pct_from_52w_high: float | None = None
    pct_from_52w_low: float | None = None
    volatility_30d: float | None = None
