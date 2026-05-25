"""Core data models shared across the pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Signal = Literal["buy", "hold", "sell"]


class Subscription(BaseModel):
    """A monitored ticker and its alert threshold."""

    ticker: str
    threshold_pct: float = Field(
        default=3.0,
        gt=0,
        description="Absolute percent move from the baseline that triggers an alert.",
    )
    notes: str | None = None


class AppConfig(BaseModel):
    """Application configuration loaded from ``config.toml``."""

    poll_interval_hours: float = Field(default=3.0, gt=0)
    db_path: str = "data/stock_spy.sqlite3"
    gemini_model: str = "gemini-2.5-flash"
    subscriptions: list[Subscription] = Field(default_factory=list)


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


class Analysis(BaseModel):
    """LLM verdict on a ticker's current situation.

    Informational only — not financial advice.
    """

    signal: Signal
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    cause: str | None = Field(
        default=None,
        description="The news or event most likely driving a price move, if any.",
    )
    significant: bool = Field(
        description="True if this warrants notifying the user right now.",
    )
