"""Tests for the swing-note prompt and agent."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from spy_core.models import NewsItem, Quote, Technicals
from swing_spy.analysis import analyze, build_prompt
from swing_spy.models import EarningsInfo, SwingNote, SwingSetup, TradePlan


def _quote() -> Quote:
    return Quote(
        ticker="MUV2.DE",
        price=468.0,
        previous_close=465.0,
        currency="EUR",
        as_of=datetime(2026, 5, 27, tzinfo=UTC),
    )


def _setup() -> SwingSetup:
    return SwingSetup(
        is_setup=True,
        kind="pullback",
        entry_low=461.0,
        entry_high=468.0,
        stop=458.0,
        target_1=492.0,
        risk_reward=2.4,
        rationale="Pulled back to support.",
    )


def _plan() -> TradePlan:
    return TradePlan(
        shares=10,
        entry=468.0,
        stop=458.0,
        target=492.0,
        cost=4680.0,
        risk_amount=100.0,
        reward_amount=240.0,
        risk_reward=2.4,
        pct_of_account=46.8,
    )


def test_prompt_grounds_in_setup_and_earnings() -> None:
    prompt = build_prompt(
        _quote(),
        Technicals(rsi_14=45.0, sma_50=470.0, sma_200=450.0),
        _setup(),
        _plan(),
        [NewsItem(ticker="MUV2.DE", title="Beat estimates", url="https://x/1", guid="1")],
        EarningsInfo(next_date=date(2026, 5, 30), days_until=3),
    )

    assert "MUV2.DE" in prompt
    assert "10 shares" in prompt
    assert "stop 458.00" in prompt
    assert "in 3 days" in prompt
    assert "Beat estimates" in prompt


def test_prompt_handles_unknown_earnings_and_no_news() -> None:
    prompt = build_prompt(_quote(), Technicals(), _setup(), _plan(), [], EarningsInfo())
    assert "Next earnings: unknown." in prompt
    assert "Recent news: none found." in prompt


async def test_analyze_returns_structured_note() -> None:
    agent = cast("Agent[None, SwingNote]", Agent("google:gemini-2.5-flash", output_type=SwingNote))
    with agent.override(model=TestModel()):
        note = await analyze(agent, _quote(), Technicals(), _setup(), _plan(), [], EarningsInfo())

    assert isinstance(note, SwingNote)
    assert 0.0 <= note.conviction <= 1.0
    assert 0.0 <= note.news_sentiment_score <= 100.0
