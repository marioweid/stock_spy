"""The scan cycle: sweep the universe for swing setups, size them, and alert on candidates.

The expensive steps (news, earnings, the LLM) run only on tickers that already passed the
deterministic setup + sizing filter, and dedup happens before the LLM, so a standing setup
costs no API calls on later cycles.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
import pandas as pd
from pydantic_ai import Agent

from spy_core.models import NewsItem, Quote, Technicals
from spy_core.notify import send_document as default_send_document
from spy_core.notify import send_message as default_send_message
from spy_core.providers.news import fetch_news as default_fetch_news
from spy_core.providers.technicals import get_technicals as default_get_technicals
from swing_spy.analysis import analyze as default_analyze
from swing_spy.earnings import get_earnings as default_get_earnings
from swing_spy.history import download_history as default_download_history
from swing_spy.history import quote_from_frame
from swing_spy.models import EarningsInfo, SwingConfig, SwingNote, SwingSetup, TradePlan
from swing_spy.report import (
    Candidate,
    candidate_signature,
    format_candidate_alert,
    render_markdown,
)
from swing_spy.setups import find_swing_setup
from swing_spy.sizing import size_position
from swing_spy.store import Store
from swing_spy.universe import get_universe

logger = logging.getLogger(__name__)

_NEWS_CONTEXT = 8

DownloadFn = Callable[[list[str]], dict[str, pd.DataFrame]]
NewsFn = Callable[[str], list[NewsItem]]
EarningsFn = Callable[[str], EarningsInfo]
AnalyzeFn = Callable[..., Awaitable[SwingNote]]
SendFn = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class _Setup:
    """A ticker that passed the deterministic filter, awaiting news/LLM enrichment."""

    quote: Quote
    technicals: Technicals
    setup: SwingSetup
    plan: TradePlan


class Scanner:
    """Runs scan cycles over the configured market universe.

    IO functions are injectable so the pipeline can be tested without network, yfinance,
    the LLM, or Telegram.
    """

    def __init__(
        self,
        config: SwingConfig,
        store: Store,
        agent: Agent[None, SwingNote],
        http_client: httpx.AsyncClient,
        *,
        telegram_token: str,
        telegram_chat_id: str,
        download_history: DownloadFn = default_download_history,
        get_technicals: Callable[..., Technicals] = default_get_technicals,
        fetch_news: NewsFn = default_fetch_news,
        get_earnings: EarningsFn = default_get_earnings,
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
        self._download_history = download_history
        self._get_technicals = get_technicals
        self._fetch_news = fetch_news
        self._get_earnings = get_earnings
        self._analyze = analyze
        self._send_message = send_message
        self._send_document = send_document

    async def run_cycle(self) -> int:
        """Scan the whole universe once and return the number of candidate alerts sent."""
        tickers = get_universe(self._config)
        logger.info("Scanning %d tickers", len(tickers))
        frames = self._download_history(tickers)
        setups = [s for s in (self._evaluate(t, f) for t, f in frames.items()) if s is not None]
        logger.info("%d setups passed the risk filter", len(setups))

        sent = 0
        for setup in setups:
            try:
                sent += await self._alert(setup)
            except Exception:
                logger.exception("Failed to alert on %s", setup.quote.ticker)
        return sent

    def evaluate_ticker(self, ticker: str, frame: pd.DataFrame) -> _Setup | None:
        """Public hook to evaluate a single ticker (used by the ``check`` command)."""
        return self._evaluate(ticker, frame)

    def _evaluate(self, ticker: str, frame: pd.DataFrame) -> _Setup | None:
        """Deterministically decide if a ticker is a sized, R:R-passing swing setup."""
        quote = quote_from_frame(ticker, frame)
        if quote is None:
            return None
        technicals = self._get_technicals(ticker, history_fn=lambda _t: frame)
        setup = find_swing_setup(technicals)
        if not setup.is_setup or setup.entry_high is None or setup.stop is None:
            return None
        if setup.target_1 is None:
            return None
        plan = size_position(
            self._config.account_balance,
            setup.entry_high,
            setup.stop,
            setup.target_1,
            risk_per_trade_pct=self._config.risk_per_trade_pct,
            max_position_pct=self._config.max_position_pct,
        )
        if plan is None or plan.risk_reward < self._config.min_risk_reward:
            return None
        return _Setup(quote=quote, technicals=technicals, setup=setup, plan=plan)

    async def _alert(self, s: _Setup) -> int:
        """Enrich a passing setup with news + LLM and send the alert, deduping by signature."""
        ticker = s.quote.ticker
        signature = candidate_signature(s.quote, s.plan)
        if not self._store.is_new_signature(ticker, signature):
            return 0

        candidate = await self.build_candidate(s)
        await self.send_candidate(candidate)
        self._store.record_alert(ticker, signature, candidate.setup.kind)
        logger.info("Alerted swing candidate %s (%s)", ticker, candidate.setup.kind)
        return 1

    async def send_candidate(self, candidate: Candidate) -> str:
        """Send a candidate's alert message + markdown report. Returns the message text."""
        ticker = candidate.quote.ticker
        text = format_candidate_alert(candidate)
        await self._send_message(self._token, self._chat_id, text, client=self._client)
        await self._send_document(
            self._token,
            self._chat_id,
            f"{ticker}_swing.md",
            render_markdown(candidate),
            caption=f"Swing candidate: {ticker}",
            client=self._client,
        )
        return text

    async def build_candidate(self, s: _Setup) -> Candidate:
        """Fetch news + earnings and run the LLM to complete a candidate."""
        news = self._fetch_news(s.quote.ticker)[:_NEWS_CONTEXT]
        earnings = self._get_earnings(s.quote.ticker)
        note = await self._analyze(
            self._agent, s.quote, s.technicals, s.setup, s.plan, news, earnings
        )
        return Candidate(
            quote=s.quote,
            technicals=s.technicals,
            setup=s.setup,
            plan=s.plan,
            note=note,
            earnings=earnings,
        )
