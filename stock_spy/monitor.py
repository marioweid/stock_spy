"""The monitor cycle: protect holdings on major events, scout swing entries, persist state."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic_ai import Agent

from stock_spy.analysis import ReportBundle, assemble_report
from stock_spy.analysis import analyze as default_analyze
from stock_spy.models import (
    AppConfig,
    EquityReport,
    Fundamentals,
    Holding,
    NewsItem,
    Quote,
    Technicals,
)
from stock_spy.notify import send_document as default_send_document
from stock_spy.notify import send_message as default_send_message
from stock_spy.providers.fundamentals import get_fundamentals as default_get_fundamentals
from stock_spy.providers.news import fetch_news as default_fetch_news
from stock_spy.providers.prices import QuoteUnavailableError
from stock_spy.providers.prices import get_quote as default_get_quote
from stock_spy.providers.technicals import get_technicals as default_get_technicals
from stock_spy.report import (
    format_opportunity_alert,
    format_protection_alert,
    format_summary,
    render_markdown,
)
from stock_spy.store import PriceBaseline, Store

logger = logging.getLogger(__name__)

_NEWS_CONTEXT = 8
_DEFAULT_THRESHOLD = 3.0

QuoteFn = Callable[[str], Quote]
NewsFn = Callable[[str], list[NewsItem]]
FundamentalsFn = Callable[[str], Fundamentals]
TechnicalsFn = Callable[[str], Technicals]
AnalyzeFn = Callable[..., Awaitable[EquityReport]]
SendFn = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class PriceDecision:
    """Outcome of evaluating a price move against its threshold and baseline."""

    should_alert: bool
    new_alerted: bool


@dataclass(frozen=True)
class _Target:
    """A ticker to process, with the holding (for protection) and watchlist context."""

    ticker: str
    holding: Holding | None
    threshold: float
    notes: str | None


def decide_price_alert(
    quote: Quote, threshold: float, baseline: PriceBaseline | None
) -> PriceDecision:
    """Decide whether a price move warrants attention, deduping within a trading day.

    A move triggers at most once per ``previous_close`` value: when the previous close
    changes (a new trading day), the flag resets.

    Args:
        quote: The current quote.
        threshold: Absolute percent move that counts as significant.
        baseline: The stored baseline for this ticker, if any.

    Returns:
        Whether to act now and the flag to persist.
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
    """Runs monitor cycles over the user's holdings and watchlist.

    IO functions are injectable so the pipeline can be tested without network, yfinance,
    the LLM, or Telegram.
    """

    def __init__(
        self,
        config: AppConfig,
        store: Store,
        agent: Agent[None, EquityReport],
        http_client: httpx.AsyncClient,
        *,
        telegram_token: str,
        telegram_chat_id: str,
        get_quote: QuoteFn = default_get_quote,
        fetch_news: NewsFn = default_fetch_news,
        get_fundamentals: FundamentalsFn = default_get_fundamentals,
        get_technicals: TechnicalsFn = default_get_technicals,
        analyze: AnalyzeFn = default_analyze,
        send_message: SendFn = default_send_message,
        send_document: SendFn = default_send_document,
    ) -> None:
        self._config = config
        self._store = store
        self._agent = agent
        self._client = http_client
        self._token = telegram_token
        self._chat_id = telegram_chat_id
        self._get_quote = get_quote
        self._fetch_news = fetch_news
        self._get_fundamentals = get_fundamentals
        self._get_technicals = get_technicals
        self._analyze = analyze
        self._send_message = send_message
        self._send_document = send_document

    def _targets(self) -> list[_Target]:
        """Merge holdings and watchlist into the set of tickers to process."""
        holdings = {h.ticker: h for h in self._config.portfolio.holdings}
        subs = {s.ticker: s for s in self._config.subscriptions}
        targets: list[_Target] = []
        for ticker in {*holdings, *subs}:
            sub = subs.get(ticker)
            targets.append(
                _Target(
                    ticker=ticker,
                    holding=holdings.get(ticker),
                    threshold=sub.threshold_pct if sub else _DEFAULT_THRESHOLD,
                    notes=sub.notes if sub else None,
                )
            )
        return targets

    async def run_cycle(self) -> int:
        """Process every holding and watchlist ticker once. Returns alerts sent."""
        sent = 0
        for target in self._targets():
            try:
                sent += await self._process(target)
            except Exception:
                logger.exception("Failed to process %s", target.ticker)
        return sent

    async def _process(self, target: _Target) -> int:
        """Evaluate one ticker and alert if it needs protection, is a setup, or moved hard."""
        try:
            quote = self._get_quote(target.ticker)
        except QuoteUnavailableError as exc:
            logger.warning("Skipping %s: %s", target.ticker, exc)
            return 0

        all_news = self._fetch_news(target.ticker)
        unseen = self._store.unseen_news(all_news)
        baseline = self._store.get_price_baseline(target.ticker)
        price = decide_price_alert(quote, target.threshold, baseline)

        alerted = 0
        if price.should_alert or unseen:
            bundle = await self._build_bundle(target, quote, all_news[:_NEWS_CONTEXT])
            if await self._maybe_alert(bundle, price.should_alert):
                alerted = 1

        self._store.mark_news_seen(unseen)
        self._store.set_price_baseline(
            target.ticker, quote.previous_close, alerted=price.new_alerted
        )
        return alerted

    async def _build_bundle(
        self, target: _Target, quote: Quote, news: list[NewsItem]
    ) -> ReportBundle:
        """Fetch fundamentals/technicals, run the LLM, and assemble the scored report."""
        fundamentals = self._get_fundamentals(target.ticker)
        technicals = self._get_technicals(target.ticker)
        report = await self._analyze(
            self._agent,
            quote,
            fundamentals,
            technicals,
            news,
            holding=target.holding,
            portfolio=self._config.portfolio,
            notes=target.notes,
        )
        return assemble_report(
            quote,
            fundamentals,
            technicals,
            report,
            holding=target.holding,
            portfolio=self._config.portfolio,
        )

    async def _maybe_alert(self, bundle: ReportBundle, price_alert: bool) -> bool:
        """Send the right alert if the situation warrants one. Returns whether one was sent."""
        decided = _decide_alert(bundle, price_alert)
        if decided is None:
            return False
        text, reason = decided
        await self._send_message(self._token, self._chat_id, text, client=self._client)
        await self._send_document(
            self._token,
            self._chat_id,
            f"{bundle.quote.ticker}_report.md",
            render_markdown(bundle),
            caption=f"Full {bundle.quote.ticker} report",
            client=self._client,
        )
        self._store.record_alert(bundle.quote.ticker, bundle.signal, reason)
        logger.info("Alerted %s (%s): %s", bundle.quote.ticker, bundle.signal, reason)
        return True


def _decide_alert(bundle: ReportBundle, price_alert: bool) -> tuple[str, str] | None:
    """Pick the alert to send, in priority order: protect, opportunity, then big move."""
    if bundle.risk is not None and bundle.risk.risk_level != "low":
        return format_protection_alert(bundle), f"Protection: {bundle.risk.risk_level} risk"
    if bundle.trade_plan is not None:
        return format_opportunity_alert(bundle), f"Swing setup ({bundle.swing.kind})"
    if price_alert:
        return format_summary(bundle), f"Price moved {bundle.quote.pct_change:+.2f}%"
    return None
