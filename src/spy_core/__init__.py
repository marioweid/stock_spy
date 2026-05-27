"""spy_core: shared market-data models, providers, Telegram delivery, and secrets.

Both leaf tools (``signal_spy``, ``swing_spy``) build on this base; it depends on neither.
"""

from __future__ import annotations

from spy_core.config import Secrets
from spy_core.models import NewsItem, Quote, Technicals
from spy_core.notify import send_document, send_message
from spy_core.providers.news import fetch_news
from spy_core.providers.technicals import get_technicals

__all__ = [
    "NewsItem",
    "Quote",
    "Secrets",
    "Technicals",
    "fetch_news",
    "get_technicals",
    "send_document",
    "send_message",
]
