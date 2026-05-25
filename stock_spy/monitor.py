"""The monitor cycle: fetch state, decide significance, analyze, alert, persist."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic_ai import Agent

from stock_spy.analysis import analyze as default_analyze
from stock_spy.models import Analysis, AppConfig, NewsItem, Quote, Subscription
from stock_spy.notify import format_alert
from stock_spy.notify import send_message as default_send_message
from stock_spy.providers.news import fetch_news as default_fetch_news
from stock_spy.providers.prices import QuoteUnavailableError
from stock_spy.providers.prices import get_quote as default_get_quote
from stock_spy.store import PriceBaseline, Store

logger = logging.getLogger(__name__)

_NEWS_CONTEXT = 8

QuoteFn = Callable[[str], Quote]
NewsFn = Callable[[str], list[NewsItem]]
AnalyzeFn = Callable[
    [Agent[None, Analysis], Quote, list[NewsItem], str | None], Awaitable[Analysis]
]
SendFn = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class PriceDecision:
    """Outcome of evaluating a price move against its threshold and baseline."""

    should_alert: bool
    new_alerted: bool


def decide_price_alert(
    quote: Quote, threshold: float, baseline: PriceBaseline | None
) -> PriceDecision:
    """Decide whether a price move warrants an alert, deduping within a trading day.

    A move alerts at most once per ``previous_close`` value: when the previous close
    changes (a new trading day), the alerted flag resets.

    Args:
        quote: The current quote.
        threshold: Absolute percent move that counts as significant.
        baseline: The stored baseline for this ticker, if any.

    Returns:
        Whether to alert now and the alerted flag to persist.
    """
    significant = abs(quote.pct_change) >= threshold
    already_alerted_today = (
        baseline is not None
        and baseline.previous_close == quote.previous_close
        and baseline.alerted
    )
    should_alert = significant and not already_alerted_today
    return PriceDecision(
        should_alert=should_alert, new_alerted=should_alert or already_alerted_today
    )


class Monitor:
    """Runs monitor cycles over the configured subscriptions.

    IO functions are injectable so the pipeline can be tested without network,
    yfinance, the LLM, or Telegram.
    """

    def __init__(
        self,
        config: AppConfig,
        store: Store,
        agent: Agent[None, Analysis],
        http_client: httpx.AsyncClient,
        *,
        telegram_token: str,
        telegram_chat_id: str,
        get_quote: QuoteFn = default_get_quote,
        fetch_news: NewsFn = default_fetch_news,
        analyze: AnalyzeFn = default_analyze,
        send_message: SendFn = default_send_message,
    ) -> None:
        self._config = config
        self._store = store
        self._agent = agent
        self._client = http_client
        self._token = telegram_token
        self._chat_id = telegram_chat_id
        self._get_quote = get_quote
        self._fetch_news = fetch_news
        self._analyze = analyze
        self._send_message = send_message

    async def run_cycle(self) -> int:
        """Process every subscription once. Returns the number of alerts sent."""
        sent = 0
        for sub in self._config.subscriptions:
            try:
                sent += await self._process(sub)
            except Exception:
                logger.exception("Failed to process %s", sub.ticker)
        return sent

    async def _process(self, sub: Subscription) -> int:
        """Evaluate a single subscription and alert if warranted."""
        try:
            quote = self._get_quote(sub.ticker)
        except QuoteUnavailableError as exc:
            logger.warning("Skipping %s: %s", sub.ticker, exc)
            return 0

        all_news = self._fetch_news(sub.ticker)
        unseen = self._store.unseen_news(all_news)
        recent = all_news[:_NEWS_CONTEXT]

        baseline = self._store.get_price_baseline(sub.ticker)
        price = decide_price_alert(quote, sub.threshold_pct, baseline)

        alerted = 0
        if price.should_alert or unseen:
            analysis = await self._analyze(self._agent, quote, recent, sub.notes)
            if price.should_alert or analysis.significant:
                reason = _reason(price.should_alert, bool(unseen), quote, sub.threshold_pct)
                await self._send_message(
                    self._token,
                    self._chat_id,
                    format_alert(quote, analysis, recent, reason),
                    client=self._client,
                )
                self._store.record_alert(sub.ticker, analysis.signal, reason)
                logger.info("Alerted %s (%s): %s", sub.ticker, analysis.signal, reason)
                alerted = 1

        self._store.mark_news_seen(unseen)
        self._store.set_price_baseline(sub.ticker, quote.previous_close, alerted=price.new_alerted)
        return alerted


def _reason(price_alert: bool, news_alert: bool, quote: Quote, threshold: float) -> str:
    """Build the short trigger-reason line shown in the alert."""
    parts: list[str] = []
    if price_alert:
        parts.append(f"Price moved {quote.pct_change:+.2f}% (threshold ±{threshold:g}%)")
    if news_alert:
        parts.append("significant news")
    if not parts:
        return "Update"
    text = " · ".join(parts)
    return text[0].upper() + text[1:]
