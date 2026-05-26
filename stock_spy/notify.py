"""Telegram delivery: send messages and attach report files via the Bot API."""

from __future__ import annotations

import httpx


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


async def send_document(
    token: str,
    chat_id: str,
    filename: str,
    content: str,
    *,
    caption: str = "",
    client: httpx.AsyncClient,
) -> None:
    """Attach a text/markdown document to a Telegram chat via the Bot API.

    Args:
        token: Telegram bot token.
        chat_id: Target chat id.
        filename: Name shown for the attachment, e.g. ``"AAPL_report.md"``.
        content: The document body (UTF-8 text).
        caption: Optional short HTML caption (Telegram limits this to ~1024 chars).
        client: An open async HTTP client.

    Raises:
        httpx.HTTPStatusError: If the Telegram API returns a non-2xx status.
    """
    response = await client.post(
        f"https://api.telegram.org/bot{token}/sendDocument",
        data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
        files={"document": (filename, content.encode("utf-8"), "text/markdown")},
    )
    response.raise_for_status()
