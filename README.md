# Stock Spy

Monitor a stock watchlist and push alerts to Telegram. Every few hours it checks each
ticker for a significant price move or significant news, then sends a Telegram message
with an LLM-generated buy / hold / sell signal and the reasoning behind it.

> Signals are **informational only — not financial advice.**

## How it works

A background service runs a cycle on an interval (default every 3h). For each ticker it:

1. fetches the latest price (yfinance) and recent news (Yahoo Finance RSS),
2. alerts if the price moved past the ticker's threshold, or if new news is significant,
3. asks Gemini (via [Pydantic AI](https://ai.pydantic.dev)) for a signal + pros/cons/cause,
4. sends a Telegram message and records state in SQLite so it never double-alerts.

## Setup

1. **Telegram bot:** message [@BotFather](https://t.me/BotFather), create a bot, copy the
   token. Send your bot a message, then read your chat id (e.g. via
   `https://api.telegram.org/bot<TOKEN>/getUpdates`).
2. **Gemini key:** create one at [Google AI Studio](https://aistudio.google.com/app/apikey).
3. **Secrets:** `cp .env.example .env` and fill in the three values.
4. **Watchlist:** edit `config.toml` — add `[[subscriptions]]` blocks with `ticker`,
   `threshold_pct`, and optional `notes`.

## Run

Locally:

```bash
uv run python -m stock_spy --once   # one cycle, then exit (good for a first test)
uv run python -m stock_spy          # start the scheduler and poll on an interval
```

With Docker (recommended for always-on):

```bash
docker compose up -d --build        # build and run detached
docker compose logs -f              # follow output
```

State persists in `./data/` and the watchlist is mounted from `./config.toml`, so you can
edit the watchlist and restart without rebuilding.

## Development

```bash
uv run pytest -q          # tests
uv run ruff check .       # lint
uv run ruff format .      # format
uv run ty check           # type check
```
