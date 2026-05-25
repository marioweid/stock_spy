"""Telegram alert formatting and delivery."""

from __future__ import annotations

from html import escape

import httpx

from stock_spy.models import Analysis, NewsItem, Quote

_DISCLAIMER = "ℹ️ Informational only — not financial advice."  # noqa: RUF001 - info emoji is intentional
_SIGNAL_LABEL = {"buy": "\U0001f7e2 BUY", "hold": "\U0001f7e1 HOLD", "sell": "\U0001f534 SELL"}
_MAX_NEWS = 3


def format_alert(quote: Quote, analysis: Analysis, news: list[NewsItem], reason: str) -> str:
    """Render an alert as Telegram HTML.

    Args:
        quote: The current quote.
        analysis: The LLM verdict.
        news: News items to link (only the first few are shown).
        reason: Short text describing what triggered the alert.

    Returns:
        An HTML string suitable for ``parse_mode=HTML``.
    """
    arrow = "\U0001f4c8" if quote.pct_change >= 0 else "\U0001f4c9"
    lines = [
        f"{arrow} <b>{escape(quote.ticker)}</b> {quote.pct_change:+.2f}% "
        f"&mdash; {_SIGNAL_LABEL.get(analysis.signal, analysis.signal.upper())}",
        f"{quote.price:.2f} {escape(quote.currency)} (prev close {quote.previous_close:.2f})",
        f"<i>{escape(reason)}</i>",
        "",
        escape(analysis.summary),
    ]
    if analysis.pros:
        lines.append("\n<b>Pros</b>")
        lines.extend(f"• {escape(p)}" for p in analysis.pros)
    if analysis.cons:
        lines.append("\n<b>Cons</b>")
        lines.extend(f"• {escape(c)}" for c in analysis.cons)
    if analysis.cause:
        lines.append(f"\n<b>Likely cause:</b> {escape(analysis.cause)}")
    if news:
        lines.append("\n<b>News</b>")
        lines.extend(
            f'• <a href="{escape(item.url)}">{escape(item.title)}</a>' for item in news[:_MAX_NEWS]
        )
    lines.append(f"\n{_DISCLAIMER}")
    return "\n".join(lines)


async def send_message(token: str, chat_id: str, text: str, *, client: httpx.AsyncClient) -> None:
    """Send an HTML message to a Telegram chat via the Bot API.

    Args:
        token: Telegram bot token.
        chat_id: Target chat id.
        text: HTML-formatted message body.
        client: An open async HTTP client.

    Raises:
        httpx.HTTPStatusError: If the Telegram API returns a non-2xx status.
    """
    response = await client.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )
    response.raise_for_status()
