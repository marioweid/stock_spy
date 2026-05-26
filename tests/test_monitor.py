"""Tests for the monitor pipeline and price-alert decision logic."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from pydantic_ai import Agent

from stock_spy.models import (
    AppConfig,
    EquityReport,
    Fundamentals,
    Holding,
    NewsItem,
    Portfolio,
    Quote,
    Subscription,
    Technicals,
)
from stock_spy.monitor import Monitor, decide_price_alert
from stock_spy.providers.prices import QuoteUnavailableError
from stock_spy.store import PriceBaseline, Store


def _quote(price: float, prev: float = 100.0) -> Quote:
    return Quote(
        ticker="AAPL", price=price, previous_close=prev, currency="USD", as_of=datetime.now(UTC)
    )


def _report() -> EquityReport:
    return EquityReport(
        summary="s",
        thesis="t",
        fundamental_view="f",
        valuation_view="v",
        technical_view="te",
        bull_case="b",
        base_case="ba",
        bear_case="be",
        conviction=0.6,
        news_sentiment_score=55.0,
        protection_note="watch the 200-day",
        opportunity_note="near support",
    )


def _news(guid: str) -> NewsItem:
    return NewsItem(ticker="AAPL", title=guid, url=f"https://x/{guid}", guid=guid)


_PULLBACK = Technicals(
    last_close=100.0,
    sma_50=99.0,
    sma_200=90.0,
    rsi_14=50.0,
    support=98.0,
    resistance=110.0,
    atr_14=3.0,
)


# --- decide_price_alert ------------------------------------------------------


def test_sub_threshold_move_does_not_alert() -> None:
    decision = decide_price_alert(_quote(102.0), threshold=3.0, baseline=None)
    assert decision.should_alert is False


def test_over_threshold_move_alerts_when_fresh() -> None:
    decision = decide_price_alert(_quote(104.0), threshold=3.0, baseline=None)
    assert decision.should_alert is True


def test_over_threshold_move_does_not_realert_same_day() -> None:
    baseline = PriceBaseline(previous_close=100.0, alerted=True)
    decision = decide_price_alert(_quote(104.0), threshold=3.0, baseline=baseline)
    assert decision.should_alert is False


# --- Monitor.run_cycle -------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(str(tmp_path / "state.sqlite3"))
    yield s
    s.close()


class _Recorder:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.documents: list[str] = []

    async def send_message(self, _token: str, _chat: str, text: str, *, client: object) -> None:
        self.messages.append(text)

    async def send_document(
        self, _token: str, _chat: str, _name: str, content: str, *, caption: str, client: object
    ) -> None:
        self.documents.append(content)


def _make_monitor(
    store: Store,
    *,
    quote: Quote,
    news: list[NewsItem],
    technicals: Technicals,
    sender: _Recorder,
    holding: Holding | None = None,
    cash: float = 0.0,
    threshold: float = 3.0,
) -> Monitor:
    holdings = [holding] if holding is not None else []
    config = AppConfig(
        subscriptions=[Subscription(ticker="AAPL", threshold_pct=threshold)],
        portfolio=Portfolio(cash=cash, holdings=holdings),
    )
    agent = cast(
        "Agent[None, EquityReport]", Agent("google:gemini-2.5-flash", output_type=EquityReport)
    )

    async def fake_analyze(*_args: object, **_kwargs: object) -> EquityReport:
        return _report()

    return Monitor(
        config,
        store,
        agent,
        httpx.AsyncClient(),
        telegram_token="T",
        telegram_chat_id="C",
        get_quote=lambda _t: quote,
        fetch_news=lambda _t: news,
        get_fundamentals=lambda _t: Fundamentals(),
        get_technicals=lambda _t: technicals,
        analyze=fake_analyze,
        send_message=sender.send_message,
        send_document=sender.send_document,
    )


async def test_holding_sharp_drop_sends_protection_alert(store: Store) -> None:
    sender = _Recorder()
    technicals = Technicals(last_close=90.0, sma_200=95.0, support=85.0)
    monitor = _make_monitor(
        store,
        quote=_quote(90.0),
        news=[],
        technicals=technicals,
        sender=sender,
        holding=Holding(ticker="AAPL", shares=10, avg_cost=100.0),
    )

    sent = await monitor.run_cycle()

    assert sent == 1
    assert "HEADS-UP" in sender.messages[0]
    assert len(sender.documents) == 1  # full report attached
    assert store.alert_count("AAPL") == 1


async def test_watchlist_setup_with_cash_sends_opportunity_alert(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(
        store,
        quote=_quote(100.0, prev=100.0),
        news=[_news("a")],
        technicals=_PULLBACK,
        sender=sender,
        cash=10_000.0,
    )

    sent = await monitor.run_cycle()

    assert sent == 1
    assert "SWING IDEA" in sender.messages[0]


async def test_big_move_without_setup_sends_summary(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(
        store, quote=_quote(105.0), news=[], technicals=Technicals(), sender=sender
    )

    sent = await monitor.run_cycle()

    assert sent == 1
    assert "/100" in sender.messages[0]


async def test_quiet_ticker_stays_silent(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(
        store, quote=_quote(101.0), news=[], technicals=Technicals(), sender=sender
    )

    sent = await monitor.run_cycle()

    assert sent == 0
    assert sender.messages == []


async def test_seen_news_does_not_trigger_analysis(store: Store) -> None:
    store.mark_news_seen([_news("a")])
    sender = _Recorder()
    monitor = _make_monitor(
        store,
        quote=_quote(100.5),
        news=[_news("a")],
        technicals=_PULLBACK,
        sender=sender,
        cash=10_000.0,
    )

    sent = await monitor.run_cycle()

    assert sent == 0


async def test_unavailable_quote_is_skipped(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(
        store, quote=_quote(105.0), news=[], technicals=Technicals(), sender=sender
    )
    monitor._get_quote = _raise_unavailable

    sent = await monitor.run_cycle()

    assert sent == 0


def _raise_unavailable(_ticker: str) -> Quote:
    raise QuoteUnavailableError("no data")
