"""Tests for the scan cycle: deterministic filtering, alerting, and dedup."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import httpx
import pandas as pd
import pytest
from pydantic_ai import Agent

from spy_core.models import Technicals
from swing_spy.models import EarningsInfo, SwingConfig, SwingNote, UniverseConfig
from swing_spy.scanner import Scanner
from swing_spy.store import Store

_PULLBACK = Technicals(
    last_close=100.0,
    sma_50=99.0,
    sma_200=90.0,
    rsi_14=50.0,
    support=98.0,
    resistance=110.0,
    atr_14=3.0,
)
_NO_SETUP = Technicals(last_close=85.0, sma_200=100.0)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"Close": [98.0, 100.0]})


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(str(tmp_path / "swing.sqlite3"))
    yield s
    s.close()


class _Recorder:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.documents: list[str] = []

    async def send_message(self, _t: str, _c: str, text: str, *, client: object) -> None:
        self.messages.append(text)

    async def send_document(
        self, _t: str, _c: str, _n: str, content: str, *, caption: str, client: object
    ) -> None:
        self.documents.append(content)


def _make_scanner(store: Store, *, technicals: Technicals, sender: _Recorder) -> Scanner:
    config = SwingConfig(
        account_balance=10_000.0,
        universe=UniverseConfig(indexes=[], extra_tickers=["AAA"]),
    )
    agent = cast("Agent[None, SwingNote]", Agent("google:gemini-2.5-flash", output_type=SwingNote))

    async def fake_analyze(*_a: object, **_k: object) -> SwingNote:
        return SwingNote(rationale="ok", news_sentiment_score=55.0, conviction=0.6)

    return Scanner(
        config,
        store,
        agent,
        httpx.AsyncClient(),
        telegram_token="T",
        telegram_chat_id="C",
        download_history=lambda _tickers: {"AAA": _frame()},
        get_technicals=lambda _t, **_k: technicals,
        fetch_news=lambda _t: [],
        get_earnings=lambda _t: EarningsInfo(),
        analyze=fake_analyze,
        send_message=sender.send_message,
        send_document=sender.send_document,
    )


async def test_setup_sends_one_alert_with_report(store: Store) -> None:
    sender = _Recorder()
    scanner = _make_scanner(store, technicals=_PULLBACK, sender=sender)

    sent = await scanner.run_cycle()

    assert sent == 1
    assert "SWING IDEA: AAA" in sender.messages[0]
    assert len(sender.documents) == 1
    assert store.alert_count("AAA") == 1


async def test_same_setup_is_not_realerted(store: Store) -> None:
    sender = _Recorder()
    scanner = _make_scanner(store, technicals=_PULLBACK, sender=sender)

    first = await scanner.run_cycle()
    second = await scanner.run_cycle()

    assert first == 1
    assert second == 0  # identical signature deduped
    assert store.alert_count("AAA") == 1


async def test_no_setup_sends_nothing(store: Store) -> None:
    sender = _Recorder()
    scanner = _make_scanner(store, technicals=_NO_SETUP, sender=sender)

    sent = await scanner.run_cycle()

    assert sent == 0
    assert sender.messages == []
