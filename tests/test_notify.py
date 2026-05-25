"""Tests for Telegram alert formatting and delivery."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from stock_spy.models import Analysis, NewsItem, Quote
from stock_spy.notify import format_alert, send_message


def _quote() -> Quote:
    return Quote(
        ticker="AAPL",
        price=110.0,
        previous_close=100.0,
        currency="USD",
        as_of=datetime.now(UTC),
    )


def _analysis(**overrides: object) -> Analysis:
    defaults: dict[str, object] = {
        "signal": "buy",
        "confidence": 0.7,
        "summary": "Strong quarter.",
        "pros": ["Revenue up"],
        "cons": ["Valuation rich"],
        "cause": "Earnings beat",
        "significant": True,
    }
    defaults.update(overrides)
    return Analysis(**defaults)  # type: ignore[arg-type]


def test_format_alert_contains_key_facts_and_disclaimer() -> None:
    news = [NewsItem(ticker="AAPL", title="Beat", url="https://x/1", guid="1")]

    msg = format_alert(_quote(), _analysis(), news, "Price up 10.00%")

    assert "<b>AAPL</b>" in msg
    assert "+10.00%" in msg
    assert "BUY" in msg
    assert "Revenue up" in msg
    assert "Valuation rich" in msg
    assert "Earnings beat" in msg
    assert '<a href="https://x/1">Beat</a>' in msg
    assert "not financial advice" in msg


def test_format_alert_escapes_html_in_dynamic_text() -> None:
    msg = format_alert(_quote(), _analysis(summary="A <b>& B"), [], "reason")

    assert "A &lt;b&gt;&amp; B" in msg


def test_format_alert_omits_empty_sections() -> None:
    msg = format_alert(_quote(), _analysis(pros=[], cons=[], cause=None), [], "reason")

    assert "Pros" not in msg
    assert "Cons" not in msg
    assert "Likely cause" not in msg


async def test_send_message_posts_to_telegram_api() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.read().decode()
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await send_message("TOKEN", "42", "<b>hi</b>", client=client)

    assert str(captured["url"]).endswith("/botTOKEN/sendMessage")
    assert "<b>hi</b>" in str(captured["json"])
    assert '"chat_id":"42"' in str(captured["json"])


async def test_send_message_raises_on_api_error() -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(400, json={"ok": False}))
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            await send_message("TOKEN", "42", "x", client=client)
        except httpx.HTTPStatusError:
            return
    raise AssertionError("expected HTTPStatusError")
