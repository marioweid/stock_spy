"""Example: run a swing analysis on Walmart (WMT) and send the result to Telegram.

Run with::

    uv run python examples/walmart.py

Secrets are read from the environment or a local ``.env`` file (see ``spy_core.config.Secrets``):
``TELEGRAM_BOT_TOKEN``, ``TELEGRAM_CHAT_ID``, and ``GEMINI_API_KEY``. No ``swing_config.toml`` is
needed — the account balance and risk rules are set inline below so the script stands alone.

The flow mirrors one ticker's path through ``swing_spy.Scanner``, but without the dedup store or
scheduler, so it always sends a message: either a full sized trade plan or a short "no setup" note.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pandas as pd

from spy_core.config import Secrets
from spy_core.models import Quote, Technicals
from spy_core.notify import send_document, send_message
from spy_core.providers.news import fetch_news
from spy_core.providers.technicals import get_technicals
from swing_spy import (
    Candidate,
    SwingConfig,
    SwingSetup,
    TradePlan,
    analyze,
    build_agent,
    download_history,
    find_swing_setup,
    format_candidate_alert,
    get_earnings,
    quote_from_frame,
    render_markdown,
    size_position,
)

TICKER = "WMT"  # Walmart on NYSE
NEWS_CONTEXT = 8
HTTP_TIMEOUT = 30.0

logger = logging.getLogger("walmart")

Evaluated = tuple[Quote, Technicals, SwingSetup, TradePlan]


def evaluate(config: SwingConfig, frame: pd.DataFrame) -> Evaluated | None:
    """Run the deterministic filter: build a quote, find a setup, and size it.

    Returns the quote, technicals, setup, and sized plan when the ticker is a clean,
    risk-passing swing entry, or ``None`` otherwise — matching ``Scanner._evaluate``.
    """
    quote = quote_from_frame(TICKER, frame)
    if quote is None:
        return None
    technicals = get_technicals(TICKER, history_fn=lambda _t: frame)
    setup = find_swing_setup(technicals)
    if not setup.is_setup or setup.entry_high is None or setup.stop is None:
        return None
    if setup.target_1 is None:
        return None
    plan = size_position(
        config.account_balance,
        setup.entry_high,
        setup.stop,
        setup.target_1,
        risk_per_trade_pct=config.risk_per_trade_pct,
        max_position_pct=config.max_position_pct,
    )
    if plan is None or plan.risk_reward < config.min_risk_reward:
        return None
    return quote, technicals, setup, plan


async def build_candidate(config: SwingConfig, secrets: Secrets, evaluated: Evaluated) -> Candidate:
    """Enrich a passing setup with news, earnings, and the Gemini narrative."""
    quote, technicals, setup, plan = evaluated
    agent = build_agent(secrets.gemini_api_key, config.gemini_model)
    news = fetch_news(TICKER)[:NEWS_CONTEXT]
    earnings = get_earnings(TICKER)
    note = await analyze(agent, quote, technicals, setup, plan, news, earnings)
    return Candidate(
        quote=quote, technicals=technicals, setup=setup, plan=plan, note=note, earnings=earnings
    )


async def main() -> None:
    """Analyse Walmart once and deliver the outcome to Telegram."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    config = SwingConfig(account_balance=10_000.0)
    secrets = Secrets()  # ty: ignore[missing-argument] - values come from env / .env

    logger.info("Downloading 1y history for %s", TICKER)
    frame = download_history([TICKER]).get(TICKER)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        token, chat = secrets.telegram_bot_token, secrets.telegram_chat_id
        if frame is None:
            await send_message(token, chat, f"⚠️ No price history for {TICKER}.", client=client)
            return

        evaluated = evaluate(config, frame)
        if evaluated is None:
            await send_message(
                token,
                chat,
                f"{TICKER} (Walmart): no clean swing setup right now.",
                client=client,
            )
            logger.info("No setup; sent a note.")
            return

        logger.info("Setup found; building candidate (news + earnings + Gemini)")
        candidate = await build_candidate(config, secrets, evaluated)
        await send_message(token, chat, format_candidate_alert(candidate), client=client)
        await send_document(
            token,
            chat,
            f"{TICKER}_swing.md",
            render_markdown(candidate),
            caption=f"Swing analysis: {TICKER} (Walmart)",
            client=client,
        )
        logger.info("Sent swing plan + report for %s", TICKER)


if __name__ == "__main__":
    asyncio.run(main())
