"""Entry point: run a single monitor cycle (--once) or start the scheduler."""

from __future__ import annotations

import argparse
import asyncio
import logging

from pydantic import ValidationError

from stock_spy.config import Secrets, load_config
from stock_spy.scheduler import run_forever, run_once


def main() -> None:
    """Parse arguments, load config, and dispatch to a single cycle or the scheduler."""
    parser = argparse.ArgumentParser(prog="stock_spy")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single monitor cycle and exit (for testing or cron).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()
    try:
        secrets = Secrets()  # ty: ignore[missing-argument] - values come from env / .env
    except ValidationError as exc:
        raise SystemExit(
            "Missing secrets. Copy .env.example to .env and set "
            "TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, and GEMINI_API_KEY.\n\n"
            f"{exc}"
        ) from exc

    if args.once:
        sent = asyncio.run(run_once(config, secrets))
        logging.getLogger("stock_spy").info("Cycle complete; %d alert(s) sent.", sent)
        return

    asyncio.run(run_forever(config, secrets))


if __name__ == "__main__":
    main()
