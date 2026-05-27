"""Tests for the quality and protection scoring engines."""

from __future__ import annotations

from datetime import UTC, datetime

from signal_spy.models import Fundamentals, Holding
from signal_spy.scoring import (
    assess_risk,
    composite,
    position_pct,
    score_fundamentals,
    score_technicals,
    verdict,
)
from spy_core.models import Quote, Technicals


def _quote(price: float, prev: float = 100.0) -> Quote:
    return Quote(
        ticker="T", price=price, previous_close=prev, currency="EUR", as_of=datetime.now(UTC)
    )


# --- quality indicator -------------------------------------------------------


def test_strong_fundamentals_score_high() -> None:
    f = Fundamentals(
        trailing_pe=12.0,
        profit_margin=0.25,
        return_on_equity=0.30,
        revenue_growth=0.20,
        debt_to_equity=20.0,
        recommendation_key="buy",
    )
    assert score_fundamentals(f) >= 75.0


def test_weak_fundamentals_score_low() -> None:
    f = Fundamentals(
        trailing_pe=80.0,
        profit_margin=-0.10,
        revenue_growth=-0.20,
        debt_to_equity=250.0,
        recommendation_key="sell",
    )
    assert score_fundamentals(f) <= 35.0


def test_empty_fundamentals_are_neutral() -> None:
    assert score_fundamentals(Fundamentals()) == 50.0


def test_uptrend_technicals_score_higher_than_downtrend() -> None:
    up = Technicals(
        last_close=110,
        sma_50=105,
        sma_200=100,
        rsi_14=62,
        macd=2,
        macd_signal=1,
        pct_from_52w_high=-3,
    )
    down = Technicals(
        last_close=90,
        sma_50=100,
        sma_200=105,
        rsi_14=28,
        macd=-2,
        macd_signal=-1,
        pct_from_52w_high=-40,
    )
    assert score_technicals(up) > score_technicals(down)


def test_empty_technicals_are_neutral() -> None:
    assert score_technicals(Technicals()) == 50.0


def test_composite_applies_weights() -> None:
    scores = composite(fundamental=80.0, technical=60.0, sentiment=50.0)
    assert scores.overall == 66.0  # 0.45*80 + 0.25*60 + 0.30*50


def test_verdict_bands() -> None:
    assert verdict(65.0) == "buy"
    assert verdict(64.9) == "hold"
    assert verdict(40.0) == "hold"
    assert verdict(39.9) == "sell"


def test_position_pct_is_clamped() -> None:
    assert position_pct(100.0, 1.0) == 5.0
    assert position_pct(0.0, 0.0) == 1.0
    assert 1.0 <= position_pct(70.0, 0.6) <= 5.0


# --- protection engine -------------------------------------------------------


def test_assess_risk_computes_money_and_critical_level() -> None:
    holding = Holding(ticker="T", shares=10, avg_cost=100.0)
    technicals = Technicals(last_close=90.0, sma_200=95.0, support=85.0)

    risk = assess_risk(_quote(90.0, prev=100.0), technicals, holding, news_sentiment=50.0)

    assert risk.todays_change == -100.0
    assert risk.unrealized_pl == -100.0
    assert risk.unrealized_pl_pct == -10.0
    assert risk.downside_to_support == 50.0  # 10 * (90 - 85)
    assert risk.risk_level == "critical"  # -10% day and below the 200-day line
    assert risk.major_event is True
    assert any("drop" in t.lower() for t in risk.triggers)


def test_assess_risk_calm_holding_is_low() -> None:
    holding = Holding(ticker="T", shares=5, avg_cost=80.0)
    technicals = Technicals(last_close=101.0, sma_200=90.0, support=95.0)

    risk = assess_risk(_quote(101.0, prev=100.5), technicals, holding, news_sentiment=60.0)

    assert risk.risk_level == "low"
    assert risk.triggers == []
