"""Tests for the analysis agent and report assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from stock_spy.analysis import analyze, assemble_report, build_prompt
from stock_spy.models import (
    EquityReport,
    Fundamentals,
    Holding,
    NewsItem,
    Portfolio,
    Quote,
    Technicals,
)


def _quote(price: float = 105.0) -> Quote:
    return Quote(
        ticker="AAPL", price=price, previous_close=100.0, currency="USD", as_of=datetime.now(UTC)
    )


def _news(title: str) -> NewsItem:
    return NewsItem(ticker="AAPL", title=title, url="https://x/1", summary="s", guid="1")


def _report(**over: object) -> EquityReport:
    defaults: dict[str, Any] = {
        "summary": "Apple makes phones.",
        "thesis": "Strong brand.",
        "fundamental_view": "Profitable.",
        "valuation_view": "Pricey.",
        "technical_view": "Uptrend.",
        "bull_case": "Up.",
        "base_case": "Flat.",
        "bear_case": "Down.",
        "conviction": 0.7,
        "news_sentiment_score": 70.0,
        "protection_note": "Watch the 200-day line.",
        "opportunity_note": "Wait for a pullback.",
    }
    defaults.update(over)
    return EquityReport(**defaults)


def test_build_prompt_includes_numbers_and_context() -> None:
    prompt = build_prompt(
        _quote(110.0),
        Fundamentals(trailing_pe=30.0),
        Technicals(rsi_14=65.0),
        [_news("Big news")],
        holding=Holding(ticker="AAPL", shares=12, avg_cost=90.0),
        portfolio=Portfolio(cash=10_000.0, base_currency="EUR"),
        notes="Apple",
    )

    assert "AAPL (Apple)" in prompt
    assert "+10.00%" in prompt
    assert "trailing_pe=30" in prompt
    assert "rsi_14=65" in prompt
    assert "OWNS this: 12 shares" in prompt
    assert "10000 EUR cash" in prompt
    assert "Big news" in prompt


def test_build_prompt_handles_no_news() -> None:
    prompt = build_prompt(_quote(), Fundamentals(), Technicals(), [])
    assert "Recent news: none found." in prompt


async def test_analyze_returns_structured_output() -> None:
    agent = cast(
        "Agent[None, EquityReport]", Agent("google:gemini-2.5-flash", output_type=EquityReport)
    )

    with agent.override(model=TestModel()):
        result = await analyze(agent, _quote(110.0), Fundamentals(), Technicals(), [_news("beat")])

    assert isinstance(result, EquityReport)
    assert 0.0 <= result.conviction <= 1.0
    assert 0.0 <= result.news_sentiment_score <= 100.0


def test_assemble_report_scores_and_sizes_a_holding() -> None:
    technicals = Technicals(
        last_close=100.0,
        sma_50=99.0,
        sma_200=90.0,
        rsi_14=50.0,
        support=98.0,
        resistance=110.0,
        atr_14=3.0,
    )
    bundle = assemble_report(
        _quote(100.0),
        Fundamentals(trailing_pe=15.0, profit_margin=0.2, recommendation_key="buy"),
        technicals,
        _report(conviction=0.8, news_sentiment_score=70.0),
        holding=Holding(ticker="AAPL", shares=10, avg_cost=80.0),
        portfolio=Portfolio(cash=10_000.0),
    )

    assert bundle.signal in ("buy", "hold", "sell")
    assert 0.0 <= bundle.scores.overall <= 100.0
    assert bundle.risk is not None  # holding present
    assert bundle.swing.is_setup is True
    assert bundle.trade_plan is not None  # cash present + valid setup


def test_assemble_report_without_holding_or_cash() -> None:
    bundle = assemble_report(
        _quote(100.0), Fundamentals(), Technicals(), _report(), holding=None, portfolio=None
    )

    assert bundle.risk is None
    assert bundle.trade_plan is None
