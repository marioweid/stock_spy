# stock_spy — Roadmap to a serious asset monitor & decision driver

## Where we are (after M2)
stock_spy can: track a real portfolio (holdings + cash), pull free data (yfinance fundamentals
+ technicals, Yahoo RSS news), score a stock 0–100 (Fundamentals/Technicals/Sentiment),
protect holdings with money-quantified risk alerts, scout swing setups with sized trade plans,
explain every metric for a beginner, and deliver a Telegram summary + full markdown report —
on demand (`report TICKER`) or on a schedule (`monitor`).

It is a solid **alerter**. To become a trustworthy **decision driver** it needs three things
it does not yet have: (1) data it can trust and enough of it, (2) evidence its signals actually
work, and (3) a portfolio-level view instead of one-stock-at-a-time. Everything below serves
those three.

## Guiding principles
- **Protection first.** The worst outcome is a silent loss. Bias toward catching real danger
  early, even at the cost of a few false alarms — but make false alarms cheap to dismiss.
- **Never fake precision.** If the data isn't there, say so. No invented options/insider/ESG
  sections. Surface uncertainty, cite sources.
- **Earn trust with evidence.** A score or a "BUY" means nothing until we've measured whether it
  predicts anything. Backtest before we believe.
- **Free-data-first, but honest about its limits.** Keep yfinance/RSS as the baseline; add paid
  feeds only where they change decisions, behind a clear interface.

---

## Phase 3 — Trust the data, see the portfolio (foundational; do first)

**Why:** the current engine reasons per-stock on delayed data with a couple of known data bugs.
A decision driver must see the whole portfolio and trust its inputs.

- **Portfolio-level analytics.** Concentration (% in one name/sector), correlation between
  holdings, total exposure vs cash, sector weights, portfolio beta. Alert on portfolio risks
  ("68% of your equity is in one stock"), not just single-name risks. *New:* `portfolio.py`
  analytics; feeds a new daily digest. This is the biggest missing decision lever.
- **Multi-currency / FX.** Today `base_currency` is cosmetic; a USD holding is shown in USD while
  cash is EUR. Add FX conversion so all money figures and totals are in the user's base currency.
  *Touches:* `models.py`, `scoring.py` (value-at-risk), `report.py`; add an FX rate provider.
- **Data validation layer.** Normalize yfinance quirks (the `dividendYield` ×100 inconsistency,
  missing/0 fields, stale `.info`). Reject or flag implausible values before they reach a report.
  *New:* validation in `providers/`. Quick win: fix dividend yield now.
- **Market context.** Pull an index (e.g. S&P 500 / MSCI World) + VIX so alerts can say "the
  whole market is down 3%, this isn't stock-specific" vs "this stock is falling alone." Hugely
  improves protection signal quality. *New:* `providers/market.py`.
- **Corporate-actions awareness.** Earnings dates, ex-dividend dates, splits — so we don't fire a
  "−7%!" panic alert on a dividend/split, and we *can* warn "earnings in 2 days, expect swings."
  *Touches:* fundamentals provider (yfinance has `calendar`/earnings dates).

## Phase 4 — Prove the signals (the credibility milestone)

**Why:** we currently *assert* the scoring weights and swing rules are sensible. Until we
measure them, the app is opinion, not a decision driver.

- **Backtesting harness.** Replay historical prices/fundamentals and measure: does a high
  composite score precede outperformance? Do swing setups hit target before stop more often than
  chance? *New:* `backtest/` using yfinance history; report hit rate, expectancy, max drawdown.
- **Signal calibration.** Tune the 45/25/30 weights and the verdict bands (`scoring.py`
  `WEIGHT_*`, `BUY_THRESHOLD`) against backtest outcomes instead of guesses. Record the chosen
  values and *why*.
- **Outcome tracking (live feedback loop).** Persist every alert/score/setup to the store, then
  later record what happened (did the protection alert precede a real drop? did the swing hit
  target?). *Touches:* `store.py` (new tables), a periodic reconciliation job. This is what lets
  the app improve over time.
- **Score history & trend.** Store daily scores per ticker so reports can say "health score fell
  72→55 over two weeks" — a far stronger decision trigger than a point-in-time number.

## Phase 5 — Protection that actually protects (robustness)

**Why:** protection is the #1 goal, but a 3-hour poll on delayed data misses fast moves.

- **Intraday monitoring** for holdings (tighter poll or an intraday data source) so gaps/flash
  drops are caught same-day, not next cycle.
- **Real stop management.** Per-holding stop levels (config), alert the moment a stop is breached,
  trailing-stop tracking, take-profit reminders. *Touches:* `models.py` (Holding gets stop),
  `monitor.py`, `scoring.py`.
- **Market-wide event detection.** Detect broad selloffs (index + breadth) and send one portfolio
  alert ("market-wide risk-off, your portfolio is −€X today") instead of N noisy single alerts.
- **Alert escalation & dedup maturity.** Current dedup is one price-baseline flag. Add per-alert
  cooldowns, escalation for critical risk (repeat until acknowledged), and snooze. *Touches:*
  `store.py`, `monitor.py`.

## Phase 6 — Smarter analysis & sizing (decision quality)

- **Volatility-aware position sizing** (ATR-based) and **portfolio heat** caps (total risk across
  open trades), accounting for existing exposure to a name. *Touches:* `scoring.py` `size_position`.
- **Better news pipeline:** more sources, full-article fetch, an actual sentiment/relevance model,
  clustering so 5 articles on one event count once. Today sentiment is a single LLM number off
  headlines. *Touches:* `providers/news.py`, `analysis.py`.
- **Earnings & estimate revisions** as first-class catalysts (surprise history, analyst revision
  trend) — strong, well-documented predictors.
- **Grounding guardrails for the LLM:** validate `price_target` against current price/analyst
  range, forbid invented figures, require it to cite which provided number each claim uses.

## Phase 7 — Interaction & delivery (usability)

- **Two-way Telegram bot:** `/report TICKER`, `/portfolio`, `/risk`, `/snooze`, inline buttons
  (acknowledge, "explain more"). Needs the bot to read updates/webhook, not just send.
- **Daily/weekly digest:** one message — portfolio value & P/L, top risks, best opportunities,
  any score changes. The habitual touchpoint most users actually want.
- **Per-alert preferences:** thresholds, quiet hours, which alert types per ticker.

## Phase 8 — Reliability & ops (make it dependable)

- **Resilience:** retries + backoff for yfinance/Gemini, caching of fundamentals (they change
  slowly), graceful degradation when a feed is down.
- **Self-monitoring:** alert the user if data feeds fail or the scheduler dies ("your monitor
  has been silent 24h"). A monitor that silently stops is worse than none.
- **LLM cost control:** cache analyses, only call Gemini when inputs materially changed.
- **Test depth:** integration tests over a recorded data fixture set, property-based tests for
  `scoring.py`, mutation testing to verify the suite catches regressions.
- **Security:** holdings + cash are sensitive. Confirm `.env`/config are gitignored, consider
  encryption at rest, never log secrets (we already redact in runs).

---

## Quick wins (small, high value, do opportunistically)
- Fix the `dividendYield` ×100 normalization in fundamentals.
- Add earnings-date awareness to suppress false earnings-day panic alerts.
- Persist daily scores to the store (enables trend lines cheaply).
- Add a `--dry-run`/console output mode for `monitor` (no Telegram) for testing.
- Market-context line in every alert ("market today: −1.2%").

## Known tech debt / rough edges (from M2)
- Delayed prices only; protection can lag fast intraday moves.
- Single-currency money math; FX not handled.
- Dedup is coarse (one price-baseline flag); no cooldown/snooze.
- News sentiment is one LLM number off headlines — no dedup, no relevance weighting.
- No evidence the scoring weights/verdict bands predict outcomes (Phase 4 addresses this).

## Decisions needed from you (will shape priorities)
1. **Paid data?** Willing to add a paid feed (real-time prices, fundamentals, options/insider) if
   it clearly improves decisions, or stay strictly free?
2. **Primary use:** mostly *protect what I hold* (favor Phases 3 & 5), or equally *find new
   trades* (favor Phases 4 & 6)?
3. **Intraday:** do you need same-day protection (Phase 5 intraday), or is end-of-day enough?
4. **Interaction:** is a daily digest + on-demand reports enough, or do you want a chat-style bot
   you can ask questions (Phase 7)?

## Suggested order
Phase 3 (foundation + portfolio view) → Phase 4 (prove signals) → Phase 5 (real protection) →
then 6/7/8 as the use-case dictates. Phases 3 and 4 are what turn this from "a nice alerter" into
"something I can base decisions on."
