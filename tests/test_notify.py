"""Tests for Telegram delivery (message + document)."""

from __future__ import annotations

import httpx

from stock_spy.notify import send_document, send_message


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


async def test_send_document_uploads_multipart() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await send_document(
            "TOKEN", "42", "AAPL_report.md", "# Report", caption="Full report", client=client
        )

    assert str(captured["url"]).endswith("/botTOKEN/sendDocument")
    body = str(captured["body"])
    assert "AAPL_report.md" in body
    assert "# Report" in body
    assert "Full report" in body


async def test_send_document_raises_on_api_error() -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(400, json={"ok": False}))
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            await send_document("TOKEN", "42", "x.md", "x", client=client)
        except httpx.HTTPStatusError:
            return
    raise AssertionError("expected HTTPStatusError")
