"""Entry point: produce a one-off report, or run the portfolio protection monitor."""

from __future__ import annotations

import argparse
import asyncio
import logging

from pydantic import ValidationError

from signal_spy.config import Secrets, load_config
from signal_spy.models import AppConfig
from signal_spy.providers.prices import QuoteUnavailableError
from signal_spy.scheduler import run_forever, run_once, run_report


def main() -> None:
    """Parse arguments, load config, and dispatch to a report or the monitor."""
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    config = load_config()
    secrets = _load_secrets()

    if args.command == "report":
        _run_report(config, secrets, args.ticker)
    elif args.once:
        sent = asyncio.run(run_once(config, secrets))
        logging.getLogger("signal_spy").info("Cycle complete; %d alert(s) sent.", sent)
    else:
        asyncio.run(run_forever(config, secrets))


def _parse_args() -> argparse.Namespace:
    """Build the ``report`` and ``monitor`` subcommands."""
    parser = argparse.ArgumentParser(prog="signal_spy")
    sub = parser.add_subparsers(dest="command", required=True)

    report_parser = sub.add_parser("report", help="Full beginner report for one ticker.")
    report_parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL.")

    monitor_parser = sub.add_parser("monitor", help="Protect holdings on price/news events.")
    monitor_parser.add_argument(
        "--once", action="store_true", help="Run a single cycle and exit (for testing or cron)."
    )
    return parser.parse_args()


def _load_secrets() -> Secrets:
    """Load secrets, turning a validation error into a clear, actionable message."""
    try:
        return Secrets()  # ty: ignore[missing-argument] - values come from env / .env
    except ValidationError as exc:
        raise SystemExit(
            "Missing secrets. Copy .env.example to .env and set "
            "TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, and GEMINI_API_KEY.\n\n"
            f"{exc}"
        ) from exc


def _run_report(config: AppConfig, secrets: Secrets, ticker: str) -> None:
    """Generate and send a report for one ticker, printing the summary."""
    try:
        summary = asyncio.run(run_report(config, secrets, ticker.upper()))
    except QuoteUnavailableError as exc:
        raise SystemExit(f"Cannot report on {ticker.upper()}: {exc}") from exc
    print(summary)


if __name__ == "__main__":
    main()
