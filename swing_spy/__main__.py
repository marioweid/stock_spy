"""Entry point: scan the market for swing candidates, or check a single ticker."""

from __future__ import annotations

import argparse
import asyncio
import logging

from pydantic import ValidationError

from swing_spy.config import Secrets, load_config
from swing_spy.scheduler import run_check, run_forever, run_once


def main() -> None:
    """Parse arguments, load config, and dispatch to the scanner or a single-ticker check."""
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    config = load_config()
    secrets = _load_secrets()

    if args.command == "check":
        print(asyncio.run(run_check(config, secrets, args.ticker.upper())))
    elif args.once:
        sent = asyncio.run(run_once(config, secrets))
        logging.getLogger("swing_spy").info("Scan complete; %d candidate alert(s) sent.", sent)
    else:
        asyncio.run(run_forever(config, secrets))


def _parse_args() -> argparse.Namespace:
    """Build the ``scan`` and ``check`` subcommands."""
    parser = argparse.ArgumentParser(prog="swing_spy")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="Scan the universe for swing candidates.")
    scan_parser.add_argument(
        "--once", action="store_true", help="Run a single scan and exit (for testing or cron)."
    )

    check_parser = sub.add_parser("check", help="Evaluate one ticker for a swing setup now.")
    check_parser.add_argument("ticker", help="Ticker symbol, e.g. MUV2.DE.")
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


if __name__ == "__main__":
    main()
