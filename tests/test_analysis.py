"""Tests for the analysis agent using Pydantic AI's TestModel."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from stock_spy.analysis import analyze, build_prompt
from stock_spy.models import Analysis, NewsItem, Quote


def _quote(pct_from: float = 105.0) -> Quote:
    return Quote(
        ticker="AAPL",
        price=pct_from,
        previous_close=100.0,
        currency="USD",
        as_of=datetime.now(UTC),
    )


def _news(title: str) -> NewsItem:
    return NewsItem(ticker="AAPL", title=title, url="https://x/1", summary="s", guid="1")


def test_build_prompt_includes_price_change_and_news() -> None:
    prompt = build_prompt(_quote(110.0), [_news("Big news")], notes="Apple")

    assert "AAPL (Apple)" in prompt
    assert "+10.00%" in prompt
    assert "Big news" in prompt


def test_build_prompt_handles_no_news() -> None:
    prompt = build_prompt(_quote(), [], notes=None)

    assert "Recent news: none found." in prompt


async def test_analyze_returns_structured_output() -> None:
    agent = cast("Agent[None, Analysis]", Agent("google:gemini-2.5-flash", output_type=Analysis))

    with agent.override(model=TestModel()):
        result = await analyze(agent, _quote(110.0), [_news("Earnings beat")], notes="Apple")

    assert isinstance(result, Analysis)
    assert result.signal in ("buy", "hold", "sell")
    assert 0.0 <= result.confidence <= 1.0
