"""News headlines via the Yahoo Finance RSS feed."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import feedparser

from stock_spy.models import NewsItem

_FEED_TEMPLATE = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


def feed_url(ticker: str) -> str:
    """Build the Yahoo Finance RSS URL for a ticker."""
    return _FEED_TEMPLATE.format(ticker=ticker)


def fetch_news(ticker: str) -> list[NewsItem]:
    """Fetch and parse recent news headlines for a ticker.

    Network errors and malformed feeds yield an empty list rather than raising,
    so one bad feed never aborts a monitor cycle.

    Args:
        ticker: The ticker symbol.

    Returns:
        Parsed news items, newest first as provided by the feed.
    """
    parsed = feedparser.parse(feed_url(ticker))
    return parse_entries(parsed, ticker)


def parse_entries(parsed: Any, ticker: str) -> list[NewsItem]:
    """Map a parsed feedparser result to :class:`NewsItem` objects.

    Pure and side-effect free so it can be tested against captured RSS fixtures.
    """
    items: list[NewsItem] = []
    for entry in getattr(parsed, "entries", []):
        link = entry.get("link", "")
        guid = entry.get("id") or link
        if not guid:
            continue
        items.append(
            NewsItem(
                ticker=ticker,
                title=entry.get("title", "").strip(),
                url=link,
                summary=entry.get("summary", "").strip(),
                published=_published_at(entry),
                guid=guid,
            )
        )
    return items


def _published_at(entry: Any) -> datetime | None:
    """Convert a feed entry's parsed time tuple to a UTC datetime, if present."""
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct is None:
        return None
    return datetime.fromtimestamp(time.mktime(struct), tz=UTC)
