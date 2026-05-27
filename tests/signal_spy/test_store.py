"""Tests for the SQLite state store."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from signal_spy.store import Store
from spy_core.models import NewsItem


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(str(tmp_path / "state.sqlite3"))
    yield s
    s.close()


def _news(guid: str, ticker: str = "AAPL") -> NewsItem:
    return NewsItem(ticker=ticker, title=guid, url=f"https://x/{guid}", guid=guid)


def test_price_baseline_absent_then_upserted(store: Store) -> None:
    assert store.get_price_baseline("AAPL") is None

    store.set_price_baseline("AAPL", 100.0, alerted=False)
    baseline = store.get_price_baseline("AAPL")
    assert baseline is not None
    assert baseline.previous_close == 100.0
    assert baseline.alerted is False

    store.set_price_baseline("AAPL", 105.0, alerted=True)
    baseline = store.get_price_baseline("AAPL")
    assert baseline is not None
    assert baseline.previous_close == 105.0
    assert baseline.alerted is True


def test_unseen_news_filters_marked_items(store: Store) -> None:
    items = [_news("a"), _news("b"), _news("c")]

    assert store.unseen_news(items) == items

    store.mark_news_seen([items[0], items[2]])
    remaining = store.unseen_news(items)

    assert [i.guid for i in remaining] == ["b"]


def test_mark_news_seen_is_idempotent(store: Store) -> None:
    item = _news("a")
    store.mark_news_seen([item])
    store.mark_news_seen([item])

    assert store.unseen_news([item]) == []


def test_record_and_count_alerts(store: Store) -> None:
    assert store.alert_count("AAPL") == 0

    store.record_alert("AAPL", "buy", "price up 4%")
    store.record_alert("AAPL", "hold", "news")

    assert store.alert_count("AAPL") == 2
    assert store.alert_count("BRK-B") == 0


def test_state_persists_across_reopen(tmp_path: Path) -> None:
    db = str(tmp_path / "state.sqlite3")
    first = Store(db)
    first.mark_news_seen([_news("a")])
    first.set_price_baseline("AAPL", 100.0, alerted=True)
    first.close()

    second = Store(db)
    assert second.unseen_news([_news("a")]) == []
    baseline = second.get_price_baseline("AAPL")
    assert baseline is not None and baseline.alerted is True
    second.close()
