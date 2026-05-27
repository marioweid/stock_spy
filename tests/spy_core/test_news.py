"""Tests for the Yahoo Finance RSS news provider."""

from __future__ import annotations

from pathlib import Path

import feedparser

from spy_core.providers.news import feed_url, parse_entries

FIXTURE = Path(__file__).parent.parent / "fixtures" / "yahoo_rss.xml"


def test_feed_url_includes_ticker() -> None:
    assert "s=AAPL" in feed_url("AAPL")


def test_parse_entries_maps_all_fields() -> None:
    parsed = feedparser.parse(FIXTURE.read_text())

    items = parse_entries(parsed, "AAPL")

    assert len(items) == 2
    first = items[0]
    assert first.ticker == "AAPL"
    assert first.title == "Apple unveils new product line"
    assert first.url == "https://finance.yahoo.com/news/apple-unveils-1.html"
    assert first.guid == "apple-unveils-1"
    assert first.summary == "Apple announced a refresh of its lineup today."
    assert first.published is not None
    assert first.published.year == 2026


def test_parse_entries_empty_feed() -> None:
    parsed = feedparser.parse("<rss version='2.0'><channel></channel></rss>")

    assert parse_entries(parsed, "AAPL") == []


def test_parse_entries_skips_entry_without_link_or_guid() -> None:
    feed = "<rss version='2.0'><channel><item><title>No identifiers</title></item></channel></rss>"
    parsed = feedparser.parse(feed)

    assert parse_entries(parsed, "AAPL") == []


def test_parse_entries_falls_back_to_link_when_no_guid() -> None:
    feed = (
        "<rss version='2.0'><channel>"
        "<item><title>Has link</title>"
        "<link>https://example.com/a</link></item>"
        "</channel></rss>"
    )
    parsed = feedparser.parse(feed)

    items = parse_entries(parsed, "AAPL")

    assert len(items) == 1
    assert items[0].guid == "https://example.com/a"
    assert items[0].published is None
