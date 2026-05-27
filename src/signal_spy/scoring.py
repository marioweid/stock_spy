"""Deterministic scoring: the quality indicator and the protection engine.

Everything here is pure and reproducible from the numbers, so the indicator a user sees can
be explained and trusted. The LLM supplies only the narrative and the news-sentiment input.
"""

from __future__ import annotations

from signal_spy.models import (
    Fundamentals,
    Holding,
    RiskAssessment,
    RiskLevel,
    Scores,
    Signal,
)
from spy_core.models import Quote, Technicals

# Composite weights — tune here. Fundamentals lead; sentiment captures fresh news.
WEIGHT_FUNDAMENTAL = 0.45
WEIGHT_TECHNICAL = 0.25
WEIGHT_SENTIMENT = 0.30

BUY_THRESHOLD = 65.0
SELL_THRESHOLD = 40.0


# --- quality indicator -------------------------------------------------------


def score_fundamentals(f: Fundamentals) -> float:
    """Blend valuation, profitability, growth, leverage, and analyst view into 0-100.

    Missing metrics are skipped and the score is the average of whatever is present, so a
    sparse profile is not penalised. Returns a neutral 50 when nothing is available.
    """
    signals = [
        _score_pe(f.trailing_pe),
        _score_peg(f.peg_ratio),
        _score_margin(f.profit_margin),
        _score_roe(f.return_on_equity),
        _score_growth(f.revenue_growth),
        _score_growth(f.earnings_growth),
        _score_debt(f.debt_to_equity),
        _score_recommendation(f.recommendation_key),
    ]
    return _average(signals)


def score_technicals(t: Technicals) -> float:
    """Blend trend, momentum, MACD, and 52-week position into 0-100."""
    signals = [
        _score_trend(t.last_close, t.sma_50, t.sma_200),
        _score_rsi(t.rsi_14),
        _score_macd(t.macd, t.macd_signal),
        _score_52w(t.pct_from_52w_high),
    ]
    return _average(signals)


def composite(fundamental: float, technical: float, sentiment: float) -> Scores:
    """Weight the three sub-scores into the headline 0-100 indicator."""
    overall = (
        WEIGHT_FUNDAMENTAL * fundamental
        + WEIGHT_TECHNICAL * technical
        + WEIGHT_SENTIMENT * sentiment
    )
    return Scores(
        fundamental=round(fundamental, 1),
        technical=round(technical, 1),
        sentiment=round(sentiment, 1),
        overall=round(overall, 1),
    )


def verdict(overall: float) -> Signal:
    """Map the overall score to a Buy/Hold/Sell signal."""
    if overall >= BUY_THRESHOLD:
        return "buy"
    if overall >= SELL_THRESHOLD:
        return "hold"
    return "sell"


def position_pct(overall: float, conviction: float) -> float:
    """Suggest a position size of 1-5% of capital from score and conviction."""
    raw = 1.0 + 4.0 * (overall / 100.0) * conviction
    return round(min(5.0, max(1.0, raw)), 1)


# --- protection engine -------------------------------------------------------


def assess_risk(
    quote: Quote, technicals: Technicals, holding: Holding, news_sentiment: float
) -> RiskAssessment:
    """Assess how exposed a holding is right now, in concrete currency terms."""
    price, shares = quote.price, holding.shares
    support = technicals.support
    downside = shares * (price - support) if support is not None and support < price else None
    triggers = _risk_triggers(quote, technicals, news_sentiment)
    below_sma200 = technicals.sma_200 is not None and price < technicals.sma_200
    return RiskAssessment(
        risk_level=_risk_level(quote.pct_change, below_sma200, len(triggers)),
        triggers=triggers,
        position_value=round(shares * price, 2),
        todays_change=round(shares * (price - quote.previous_close), 2),
        unrealized_pl=round(shares * (price - holding.avg_cost), 2),
        unrealized_pl_pct=round((price - holding.avg_cost) / holding.avg_cost * 100.0, 1),
        downside_to_support=None if downside is None else round(downside, 2),
    )


def _risk_triggers(quote: Quote, t: Technicals, news_sentiment: float) -> list[str]:
    """Build the plain-language list of things going wrong for a holding."""
    triggers: list[str] = []
    pct = quote.pct_change
    if pct <= -5:
        triggers.append(f"Sharp drop today: {pct:.1f}%.")
    elif pct <= -3:
        triggers.append(f"Notable drop today: {pct:.1f}%.")
    if t.sma_200 is not None and quote.price < t.sma_200:
        triggers.append("Price fell below its 200-day average, a long-term support line.")
    if t.recent_swing_low is not None and quote.price < t.recent_swing_low:
        triggers.append("Price broke below its recent low.")
    if t.atr_14 and quote.price and t.atr_14 / quote.price > 0.05:
        triggers.append("Trading unusually wildly (high day-to-day swings).")
    if news_sentiment < 35:
        triggers.append("Recent news has turned negative.")
    return triggers


def _risk_level(pct_change: float, below_sma200: bool, num_triggers: int) -> RiskLevel:
    """Combine the day's move, trend break, and trigger count into a risk level."""
    if pct_change <= -8 or (below_sma200 and pct_change <= -5):
        return "critical"
    if pct_change <= -5 or below_sma200 or num_triggers >= 2:
        return "high"
    if num_triggers >= 1:
        return "elevated"
    return "low"


# --- sub-score helpers -------------------------------------------------------


def _average(signals: list[float | None]) -> float:
    """Average the present signals, or 50 (neutral) if none are available."""
    present = [s for s in signals if s is not None]
    return round(sum(present) / len(present), 1) if present else 50.0


def _score_pe(pe: float | None) -> float | None:
    if pe is None:
        return None
    if pe < 0:
        return 25.0
    for ceiling, score in ((10, 95.0), (15, 85.0), (25, 70.0), (35, 50.0), (50, 32.0)):
        if pe <= ceiling:
            return score
    return 18.0


def _score_peg(peg: float | None) -> float | None:
    if peg is None or peg <= 0:
        return None
    for ceiling, score in ((1, 90.0), (2, 65.0), (3, 45.0)):
        if peg <= ceiling:
            return score
    return 30.0


def _score_margin(margin: float | None) -> float | None:
    if margin is None:
        return None
    if margin < 0:
        return 12.0
    for ceiling, score in ((0.05, 40.0), (0.10, 55.0), (0.20, 72.0)):
        if margin < ceiling:
            return score
    return 90.0


def _score_roe(roe: float | None) -> float | None:
    if roe is None:
        return None
    if roe < 0:
        return 15.0
    for ceiling, score in ((0.05, 40.0), (0.15, 60.0), (0.30, 80.0)):
        if roe < ceiling:
            return score
    return 92.0


def _score_growth(growth: float | None) -> float | None:
    if growth is None:
        return None
    for ceiling, score in ((-0.10, 15.0), (0.0, 35.0), (0.05, 50.0), (0.15, 68.0), (0.30, 82.0)):
        if growth < ceiling:
            return score
    return 92.0


def _score_debt(debt_to_equity: float | None) -> float | None:
    if debt_to_equity is None or debt_to_equity < 0:
        return None
    for ceiling, score in ((30, 90.0), (60, 78.0), (100, 62.0), (200, 45.0)):
        if debt_to_equity < ceiling:
            return score
    return 25.0


_RECOMMENDATION_SCORES = {
    "strong_buy": 90.0,
    "buy": 78.0,
    "outperform": 75.0,
    "hold": 52.0,
    "neutral": 52.0,
    "underperform": 30.0,
    "sell": 20.0,
    "strong_sell": 12.0,
}


def _score_recommendation(key: str | None) -> float | None:
    if key is None:
        return None
    return _RECOMMENDATION_SCORES.get(key.lower().replace(" ", "_"))


def _score_trend(price: float | None, sma50: float | None, sma200: float | None) -> float | None:
    if price is None or (sma50 is None and sma200 is None):
        return None
    above = sum((sma50 is not None and price > sma50, sma200 is not None and price > sma200))
    if above == 2:
        return 85.0
    if above == 1:
        return 58.0
    return 28.0


def _score_rsi(rsi: float | None) -> float | None:
    if rsi is None:
        return None
    for ceiling, score in ((30, 35.0), (45, 48.0), (55, 62.0), (70, 75.0), (80, 58.0)):
        if rsi < ceiling:
            return score
    return 45.0


def _score_macd(macd: float | None, signal: float | None) -> float | None:
    if macd is None or signal is None:
        return None
    return 72.0 if macd > signal else 40.0


def _score_52w(pct_from_high: float | None) -> float | None:
    if pct_from_high is None:
        return None
    for floor_pct, score in ((-5, 80.0), (-15, 65.0), (-30, 50.0)):
        if pct_from_high >= floor_pct:
            return score
    return 35.0
