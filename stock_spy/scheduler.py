"""Wiring and scheduling: build the monitor, run it, or produce a one-off report."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from stock_spy.analysis import analyze, assemble_report, build_agent
from stock_spy.config import Secrets
from stock_spy.models import AppConfig
from stock_spy.monitor import Monitor
from stock_spy.notify import send_document, send_message
from stock_spy.providers.fundamentals import get_fundamentals
from stock_spy.providers.news import fetch_news
from stock_spy.providers.prices import get_quote
from stock_spy.providers.technicals import get_technicals
from stock_spy.report import format_summary, render_markdown
from stock_spy.store import Store

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 30.0
_NEWS_CONTEXT = 8


@asynccontextmanager
async def build_monitor(config: AppConfig, secrets: Secrets) -> AsyncIterator[Monitor]:
    """Construct a fully wired monitor, cleaning up the store and HTTP client on exit."""
    store = Store(config.db_path)
    try:
        agent = build_agent(secrets.gemini_api_key, config.gemini_model)
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            yield Monitor(
                config,
                store,
                agent,
                client,
                telegram_token=secrets.telegram_bot_token,
                telegram_chat_id=secrets.telegram_chat_id,
            )
    finally:
        store.close()


async def run_once(config: AppConfig, secrets: Secrets) -> int:
    """Run a single monitor cycle and return the number of alerts sent."""
    async with build_monitor(config, secrets) as monitor:
        return await monitor.run_cycle()


async def run_forever(config: AppConfig, secrets: Secrets) -> None:
    """Run an immediate cycle, then keep polling every ``poll_interval_hours``."""
    async with build_monitor(config, secrets) as monitor:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            monitor.run_cycle,
            "interval",
            hours=config.poll_interval_hours,
            next_run_time=datetime.now(),
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        logger.info("Scheduler started; polling every %gh", config.poll_interval_hours)
        await asyncio.Event().wait()


async def run_report(config: AppConfig, secrets: Secrets, ticker: str) -> str:
    """Produce a full report for one ticker, send it to Telegram, and return the summary.

    Args:
        config: Loaded application configuration (provides portfolio context).
        secrets: Telegram + Gemini credentials.
        ticker: The ticker symbol to analyze.

    Returns:
        The Telegram summary text (also useful to print).

    Raises:
        QuoteUnavailableError: If no price data exists for the ticker.
    """
    agent = build_agent(secrets.gemini_api_key, config.gemini_model)
    holding = next((h for h in config.portfolio.holdings if h.ticker == ticker), None)
    notes = next((s.notes for s in config.subscriptions if s.ticker == ticker), None)

    quote = get_quote(ticker)
    fundamentals = get_fundamentals(ticker)
    technicals = get_technicals(ticker)
    report = await analyze(
        agent,
        quote,
        fundamentals,
        technicals,
        fetch_news(ticker)[:_NEWS_CONTEXT],
        holding=holding,
        portfolio=config.portfolio,
        notes=notes,
    )
    bundle = assemble_report(
        quote, fundamentals, technicals, report, holding=holding, portfolio=config.portfolio
    )
    summary = format_summary(bundle)
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        await send_message(
            secrets.telegram_bot_token, secrets.telegram_chat_id, summary, client=client
        )
        await send_document(
            secrets.telegram_bot_token,
            secrets.telegram_chat_id,
            f"{ticker}_report.md",
            render_markdown(bundle),
            caption=f"Full {ticker} report",
            client=client,
        )
    return summary
