"""Wiring and scheduling: build the scanner, run a cycle, or evaluate a single ticker."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from swing_spy.analysis import build_agent
from swing_spy.config import Secrets
from swing_spy.dashboard_candidates import candidate_to_snapshot
from swing_spy.history import download_history
from swing_spy.models import SwingConfig
from swing_spy.report import Candidate
from swing_spy.scanner import Scanner
from swing_spy.store import Store
from swing_spy.trade_lifecycle import TradeLifecycleService
from swing_spy.trade_store import TradeStore

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 30.0


@asynccontextmanager
async def build_scanner(config: SwingConfig, secrets: Secrets) -> AsyncIterator[Scanner]:
    """Construct a fully wired scanner, cleaning up the store and HTTP client on exit."""
    store = Store(config.db_path)
    trade_store = TradeStore(config.db_path)
    trade_service = TradeLifecycleService(trade_store)

    def record_dashboard_candidate(candidate: Candidate) -> None:
        trade_service.record_candidate(candidate_to_snapshot(candidate))

    try:
        agent = build_agent(secrets.gemini_api_key, config.gemini_model)
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            yield Scanner(
                config,
                store,
                agent,
                client,
                telegram_token=secrets.telegram_bot_token,
                telegram_chat_id=secrets.telegram_chat_id,
                record_dashboard_candidate=record_dashboard_candidate,
            )
    finally:
        trade_store.close()
        store.close()


async def run_once(config: SwingConfig, secrets: Secrets) -> int:
    """Run a single scan cycle and return the number of candidate alerts sent."""
    async with build_scanner(config, secrets) as scanner:
        return await scanner.run_cycle()


async def run_forever(config: SwingConfig, secrets: Secrets) -> None:
    """Run an immediate scan, then keep scanning every ``poll_interval_hours``."""
    async with build_scanner(config, secrets) as scanner:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            scanner.run_cycle,
            "interval",
            hours=config.poll_interval_hours,
            next_run_time=datetime.now(),
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        logger.info("Scanner started; scanning every %gh", config.poll_interval_hours)
        await asyncio.Event().wait()


async def run_check(config: SwingConfig, secrets: Secrets, ticker: str) -> str:
    """Evaluate one ticker now: if it is a setup, send the alert and return its text.

    Returns:
        The Telegram alert text if the ticker is a sized swing setup, else a plain note.
    """
    async with build_scanner(config, secrets) as scanner:
        frames = download_history([ticker])
        frame = frames.get(ticker)
        if frame is None:
            return f"No price history available for {ticker}."
        evaluated = scanner.evaluate_ticker(ticker, frame)
        if evaluated is None:
            return f"{ticker}: no clean swing setup right now."
        candidate = await scanner.build_candidate(evaluated)
        if scanner.record_dashboard_candidate is not None:
            scanner.record_dashboard_candidate(candidate)
        return await scanner.send_candidate(candidate)
