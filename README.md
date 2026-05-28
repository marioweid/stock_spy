# Spy Tools

Telegram-alerting tools built on a shared core. Two domain leaves, one base:

- **`spy_core`** — shared library: market-data models (`Quote`, `NewsItem`, `Technicals`),
  the generic providers both leaves use (news, technicals), Telegram delivery, and secrets.
- **`signal_spy`** — a **portfolio guardian**. Watches the stocks you own (and a watchlist) for
  significant price moves or news, and sends a Telegram message with an LLM-generated
  buy / hold / sell signal, a 0–100 quality score, and protection heads-ups on what you hold.
- **`swing_spy`** — a **market scanner**. Sweeps a universe of DAX 40 + S&P 500 names for
  swing-trade setups and alerts you on candidates with a concrete plan: entry, shares to buy,
  a stop-loss sized to ~1% account risk, and a target.

Each leaf is a library first — `from swing_spy import Scanner, get_universe` or
`from signal_spy import Monitor` — with a thin CLI on top. `signal_spy` and `swing_spy` never
import each other; both depend only on `spy_core`.

> Everything here is **informational only — not financial advice.**

## How it works

Both leaves run a cycle on an interval and record state in SQLite so they never double-alert.

**signal_spy** — for each watched ticker: fetch price (yfinance) + news (Yahoo RSS), alert on a
threshold move or fresh news, ask Gemini (via [Pydantic AI](https://ai.pydantic.dev)) for a
narrative, and send a scored summary or a protection alert for holdings.

**swing_spy** — batch-download history for the whole universe, detect swing setups
deterministically (uptrend pullback / oversold bounce), size each at ~1% risk, and reject weak
risk/reward. Only the handful that pass get news + an earnings check + a short Gemini rationale,
then a candidate alert. The LLM never runs on the whole universe.

## Setup

1. **Telegram bot:** message [@BotFather](https://t.me/BotFather), create a bot, copy the
   token. Send your bot a message, then read your chat id (e.g. via
   `https://api.telegram.org/bot<TOKEN>/getUpdates`).
2. **Gemini key:** create one at [Google AI Studio](https://aistudio.google.com/app/apikey).
3. **Secrets:** `cp .env.example .env` and fill in the three values (shared by both leaves).
4. **Portfolio / watchlist:** `cp signal_config_example.toml signal_config.toml`, then edit it
   (`[[portfolio.holdings]]`, `[[subscriptions]]`). The real config is gitignored.
5. **Scanner:** `cp swing_config_example.toml swing_config.toml`, then edit it — set
   `account_balance` to your real number and pick the `[universe]` indexes (`"DAX40"`,
   `"SP500"`) plus any `extra_tickers`.

## Run

Locally (each leaf is its own `uv` command, or run via `python -m`):

```bash
# Portfolio guardian
uv run signal-spy monitor --once       # one cycle, then exit
uv run signal-spy monitor              # poll on an interval
uv run signal-spy report AAPL          # full one-off report for a ticker

# Market scanner
uv run swing-spy scan --once           # one scan, then exit
uv run swing-spy scan                  # poll on an interval
uv run swing-spy check MUV2.DE         # evaluate a single ticker now

# Swing dashboard
uv run swing-spy scan --once           # persist candidate snapshots first
uv run streamlit run src/swing_spy/streamlit_app/app.py
```

With Docker (recommended for always-on) — runs both services from one image:

```bash
docker compose up -d --build        # build and run both detached
docker compose logs -f              # follow output
```

State persists in `./data/`; `signal_config.toml` and `swing_config.toml` are mounted, so you
can edit them and restart without rebuilding.

## Development

```bash
uv run pytest -q          # tests
uv run ruff check .       # lint
uv run ruff format .      # format
uv run ty check           # type check
```
