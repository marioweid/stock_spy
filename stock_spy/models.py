"""Core data models shared across the pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Signal = Literal["buy", "hold", "sell"]
RiskLevel = Literal["low", "elevated", "high", "critical"]
SetupKind = Literal["pullback", "oversold_bounce", "none"]


class Subscription(BaseModel):
    """A watched ticker scanned for swing-trade opportunities."""

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
    """The user's real portfolio: what they own and the cash they can deploy."""

    cash: float = Field(default=0.0, ge=0, description="Cash available for new swing trades.")
    base_currency: str = "EUR"
    risk_per_trade_pct: float = Field(
        default=1.5, gt=0, le=100, description="Percent of cash risked on a single swing trade."
    )
    max_position_pct: float = Field(
        default=20.0, gt=0, le=100, description="Cap on cash committed to one position."
    )
    holdings: list[Holding] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Application configuration loaded from ``config.toml``."""

    poll_interval_hours: float = Field(default=3.0, gt=0)
    db_path: str = "data/stock_spy.sqlite3"
    gemini_model: str = "gemini-2.5-flash"
    subscriptions: list[Subscription] = Field(default_factory=list)
    portfolio: Portfolio = Field(default_factory=Portfolio)


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
    opportunity_note: str = Field(description="Plain-language: is this a swing entry, and why.")


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


class SwingSetup(BaseModel):
    """Whether a ticker currently shows a tradeable swing entry."""

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
    """A concrete, risk-sized swing trade derived from a setup and the user's cash."""

    shares: int
    entry: float
    stop: float
    target: float
    cost: float = Field(description="shares * entry, in quote currency.")
    risk_amount: float = Field(description="Loss if stopped out: shares * (entry - stop).")
    reward_amount: float = Field(description="Gain at target: shares * (target - entry).")
    risk_reward: float
    pct_of_cash: float
