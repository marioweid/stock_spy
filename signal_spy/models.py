"""Domain models for the signal tool: portfolio, config, scores, and the LLM equity report.

Market-data primitives (Quote, NewsItem, Technicals) live in :mod:`spy_core.models`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Signal = Literal["buy", "hold", "sell"]
RiskLevel = Literal["low", "elevated", "high", "critical"]


class Subscription(BaseModel):
    """A watched ticker scanned for significant price moves and news."""

    ticker: str
    threshold_pct: float = Field(
        default=3.0,
        gt=0,
        description="Absolute percent move from the baseline that triggers a price alert.",
    )
    notes: str | None = None


class Holding(BaseModel):
    """A position the user actually owns, used for protection alerts."""

    ticker: str
    shares: float = Field(gt=0)
    avg_cost: float = Field(gt=0, description="Average price paid per share.")


class Portfolio(BaseModel):
    """The user's real portfolio: the positions watched for protection alerts."""

    base_currency: str = "EUR"
    holdings: list[Holding] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Application configuration loaded from ``signal_config.toml``."""

    poll_interval_hours: float = Field(default=3.0, gt=0)
    db_path: str = "data/signal_spy.sqlite3"
    gemini_model: str = "gemini-2.5-flash"
    subscriptions: list[Subscription] = Field(default_factory=list)
    portfolio: Portfolio = Field(default_factory=Portfolio)


class Fundamentals(BaseModel):
    """Company financial metrics from yfinance ``.info``; any field may be missing."""

    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    peg_ratio: float | None = None
    profit_margin: float | None = None
    gross_margin: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    return_on_equity: float | None = None
    debt_to_equity: float | None = None
    beta: float | None = None
    market_cap: float | None = None
    target_mean_price: float | None = None
    target_high_price: float | None = None
    target_low_price: float | None = None
    recommendation_key: str | None = None
    num_analysts: int | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    dividend_yield: float | None = None
    free_cashflow: float | None = None
    total_revenue: float | None = None


class Catalyst(BaseModel):
    """An upcoming event that could move the stock."""

    title: str
    timeframe: str = Field(description="When it is expected, e.g. 'next earnings' or '1-3 months'.")
    impact: str = Field(description="'positive', 'negative', or 'mixed' with a short reason.")


class EquityReport(BaseModel):
    """The LLM's structured, beginner-friendly view. Informational, not financial advice.

    The headline Buy/Hold/Sell is derived from objective scores, not from this object; the
    model supplies narrative, conviction, price target, and the news sentiment sub-score.
    """

    summary: str = Field(description="One short plain-language paragraph a beginner can follow.")
    thesis: str
    fundamental_view: str
    valuation_view: str
    technical_view: str
    catalysts: list[Catalyst] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    bull_case: str
    base_case: str
    bear_case: str
    price_target: float | None = None
    conviction: float = Field(ge=0.0, le=1.0, description="How sure the analysis is, 0-1.")
    news_sentiment_score: float = Field(
        ge=0.0, le=100.0, description="Tone of recent news: 0 very negative, 50 neutral, 100 great."
    )
    protection_note: str = Field(description="Plain-language: what an owner should watch for.")


class Scores(BaseModel):
    """The 0-100 quality indicator and its three transparent sub-scores."""

    fundamental: float = Field(ge=0.0, le=100.0)
    technical: float = Field(ge=0.0, le=100.0)
    sentiment: float = Field(ge=0.0, le=100.0)
    overall: float = Field(ge=0.0, le=100.0)


class RiskAssessment(BaseModel):
    """Protection view for a holding: how exposed the user is right now."""

    risk_level: RiskLevel
    triggers: list[str] = Field(default_factory=list)
    position_value: float = Field(description="Current market value of the holding.")
    todays_change: float = Field(description="Gain/loss on the holding today, in quote currency.")
    unrealized_pl: float = Field(description="Gain/loss vs average cost, in quote currency.")
    unrealized_pl_pct: float
    downside_to_support: float | None = Field(
        default=None, description="Loss if price fell to support, in quote currency."
    )

    @property
    def major_event(self) -> bool:
        """True when the risk warrants an urgent heads-up."""
        return self.risk_level in ("high", "critical")
