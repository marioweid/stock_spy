"""Data models for the swing scanner: config, setups, sized plans, and the LLM note."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SetupKind = Literal["pullback", "oversold_bounce", "none"]


class UniverseConfig(BaseModel):
    """Which symbol lists make up the scanned market, plus any one-off additions."""

    indexes: list[str] = Field(default_factory=lambda: ["DAX40", "SP500"])
    extra_tickers: list[str] = Field(default_factory=list)


class SwingConfig(BaseModel):
    """Scanner configuration loaded from ``swing_config.toml``."""

    poll_interval_hours: float = Field(default=6.0, gt=0)
    db_path: str = "data/swing_spy.sqlite3"
    gemini_model: str = "gemini-2.5-flash"
    account_balance: float = Field(
        default=10000.0, gt=0, description="Capital that position sizes are computed against."
    )
    risk_per_trade_pct: float = Field(
        default=1.0, gt=0, le=100, description="Percent of the account risked if the stop is hit."
    )
    max_position_pct: float = Field(
        default=50.0, gt=0, le=100, description="Cap on capital committed to one position."
    )
    min_risk_reward: float = Field(
        default=1.5, gt=0, description="Reject setups whose reward-to-risk is below this."
    )
    universe: UniverseConfig = Field(default_factory=UniverseConfig)


class SwingSetup(BaseModel):
    """Whether a ticker currently shows a tradeable swing entry, and its levels."""

    is_setup: bool
    kind: SetupKind = "none"
    entry_low: float | None = None
    entry_high: float | None = None
    stop: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    risk_reward: float | None = None
    rationale: str = ""


class TradePlan(BaseModel):
    """A concrete, risk-sized swing trade derived from a setup and the account balance."""

    shares: int
    entry: float
    stop: float
    target: float
    cost: float = Field(description="shares * entry, in quote currency.")
    risk_amount: float = Field(description="Loss if stopped out: shares * (entry - stop).")
    reward_amount: float = Field(description="Gain at target: shares * (target - entry).")
    risk_reward: float
    pct_of_account: float


class SwingNote(BaseModel):
    """The LLM's short, plain-language view of a candidate. Informational, not advice."""

    rationale: str = Field(description="A few sentences a beginner can follow on why this setup.")
    news_sentiment_score: float = Field(
        ge=0.0, le=100.0, description="Tone of recent news: 0 very negative, 50 neutral, 100 great."
    )
    conviction: float = Field(ge=0.0, le=1.0, description="How sure the read is, 0-1.")


class EarningsInfo(BaseModel):
    """Next scheduled earnings date for a ticker, if known, and days until then."""

    next_date: date | None = None
    days_until: int | None = None

    @property
    def is_imminent(self) -> bool:
        """True when earnings fall inside the next week — a reason to be cautious."""
        return self.days_until is not None and 0 <= self.days_until <= 7
