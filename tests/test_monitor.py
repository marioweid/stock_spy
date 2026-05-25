"""Tests for the monitor pipeline and price-alert decision logic."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from pydantic_ai import Agent

from stock_spy.models import Analysis, AppConfig, NewsItem, Quote, Subscription
from stock_spy.monitor import Monitor, decide_price_alert
from stock_spy.providers.prices import QuoteUnavailableError
from stock_spy.store import PriceBaseline, Store


def _quote(price: float, prev: float = 100.0) -> Quote:
    return Quote(
        ticker="AAPL", price=price, previous_close=prev, currency="USD", as_of=datetime.now(UTC)
    )


def _analysis(significant: bool) -> Analysis:
    return Analysis(signal="hold", confidence=0.5, summary="s", significant=significant)


def _news(guid: str) -> NewsItem:
    return NewsItem(ticker="AAPL", title=guid, url=f"https://x/{guid}", guid=guid)


# --- decide_price_alert ------------------------------------------------------


def test_sub_threshold_move_does_not_alert() -> None:
    decision = decide_price_alert(_quote(102.0), threshold=3.0, baseline=None)
    assert decision.should_alert is False
    assert decision.new_alerted is False


def test_over_threshold_move_alerts_when_fresh() -> None:
    decision = decide_price_alert(_quote(104.0), threshold=3.0, baseline=None)
    assert decision.should_alert is True
    assert decision.new_alerted is True


def test_over_threshold_move_does_not_realert_same_day() -> None:
    baseline = PriceBaseline(previous_close=100.0, alerted=True)
    decision = decide_price_alert(_quote(104.0), threshold=3.0, baseline=baseline)
    assert decision.should_alert is False
    assert decision.new_alerted is True


def test_new_trading_day_resets_alerted() -> None:
    baseline = PriceBaseline(previous_close=90.0, alerted=True)
    decision = decide_price_alert(_quote(104.0, prev=100.0), threshold=3.0, baseline=baseline)
    assert decision.should_alert is True


# --- Monitor.run_cycle -------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(str(tmp_path / "state.sqlite3"))
    yield s
    s.close()


class _Recorder:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, _token: str, _chat: str, text: str, *, client: object) -> None:
        self.messages.append(text)


def _make_monitor(
    store: Store,
    *,
    quote: Quote,
    news: list[NewsItem],
    significant: bool,
    sender: _Recorder,
    threshold: float = 3.0,
) -> Monitor:
    config = AppConfig(subscriptions=[Subscription(ticker="AAPL", threshold_pct=threshold)])
    agent = cast("Agent[None, Analysis]", Agent("google:gemini-2.5-flash", output_type=Analysis))

    async def fake_analyze(_agent, _quote, _news, _notes):
        return _analysis(significant)

    return Monitor(
        config,
        store,
        agent,
        httpx.AsyncClient(),
        telegram_token="T",
        telegram_chat_id="C",
        get_quote=lambda _t: quote,
        fetch_news=lambda _t: news,
        analyze=fake_analyze,
        send_message=sender.send,
    )


async def test_price_move_over_threshold_alerts(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(store, quote=_quote(105.0), news=[], significant=False, sender=sender)

    sent = await monitor.run_cycle()

    assert sent == 1
    assert "AAPL" in sender.messages[0]
    assert store.alert_count("AAPL") == 1


async def test_significant_news_alerts(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(
        store, quote=_quote(100.5), news=[_news("a")], significant=True, sender=sender
    )

    sent = await monitor.run_cycle()

    assert sent == 1
    assert store.unseen_news([_news("a")]) == []  # marked seen


async def test_seen_news_does_not_realert(store: Store) -> None:
    store.mark_news_seen([_news("a")])
    sender = _Recorder()
    monitor = _make_monitor(
        store, quote=_quote(100.5), news=[_news("a")], significant=True, sender=sender
    )

    sent = await monitor.run_cycle()

    assert sent == 0
    assert sender.messages == []


async def test_sub_threshold_move_stays_silent(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(store, quote=_quote(101.0), news=[], significant=False, sender=sender)

    sent = await monitor.run_cycle()

    assert sent == 0
    assert sender.messages == []


async def test_insignificant_news_stays_silent(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(
        store, quote=_quote(100.5), news=[_news("a")], significant=False, sender=sender
    )

    sent = await monitor.run_cycle()

    assert sent == 0
    assert store.unseen_news([_news("a")]) == []  # still marked seen so we skip it next time


async def test_unavailable_quote_is_skipped(store: Store) -> None:
    sender = _Recorder()
    monitor = _make_monitor(store, quote=_quote(105.0), news=[], significant=False, sender=sender)
    monitor._get_quote = _raise_unavailable

    sent = await monitor.run_cycle()

    assert sent == 0


def _raise_unavailable(_ticker: str) -> Quote:
    raise QuoteUnavailableError("no data")
