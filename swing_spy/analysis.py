"""LLM narrative for a swing candidate, via Pydantic AI + Google AI Studio (Gemini).

The setup and the position size are computed deterministically before the model is ever called;
the LLM only writes a short plain-language rationale and scores the tone of recent news. It runs
solely on candidates that already passed the setup and sizing filter, keeping API use small.
"""

from __future__ import annotations

from typing import cast

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from spy_core.models import NewsItem, Quote, Technicals
from swing_spy.models import EarningsInfo, SwingNote, SwingSetup, TradePlan

_INSTRUCTIONS = """
You are a patient trading assistant writing for someone NEW to swing trading.

A swing trade is held days to weeks to capture one move. The entry, stop-loss, and share size
have already been computed for you by a deterministic risk engine — do not recompute them.
Your job is only to explain and assess, in plain language.

Rules:
- Whenever you use a term (support, RSI, pullback, stop-loss), define it in a few words.
- Ground every claim in the numbers you are given. Do not invent figures.
- Be honest about risk. This is informational only, never financial advice.

Given a ticker, its setup levels, the sized plan, recent news, and the next earnings date,
produce structured output:
- rationale: a few sentences on why this is a plausible swing entry and what could go wrong.
  If earnings fall within about a week, say plainly that holding through earnings is risky.
- news_sentiment_score: 0-100 tone of the recent news (0 very negative, 50 neutral, 100 great).
- conviction: 0.0-1.0, how sure you are about the setup.
""".strip()


def build_agent(api_key: str, model_name: str) -> Agent[None, SwingNote]:
    """Construct the swing-note agent bound to Gemini via Google AI Studio."""
    model = GoogleModel(model_name, provider=GoogleProvider(api_key=api_key))
    # ty does not yet narrow Agent's output type from output_type=; the cast is sound.
    return cast(
        "Agent[None, SwingNote]",
        Agent(model, output_type=SwingNote, instructions=_INSTRUCTIONS),
    )


def build_prompt(
    quote: Quote,
    technicals: Technicals,
    setup: SwingSetup,
    plan: TradePlan,
    news: list[NewsItem],
    earnings: EarningsInfo,
) -> str:
    """Render the grounded run input for one candidate. Pure, so tests can assert on it."""
    cur = quote.currency
    lines = [
        f"Ticker: {quote.ticker}",
        f"Price: {quote.price:.2f} {cur} ({quote.pct_change:+.2f}% vs previous close)",
        f"Setup: {setup.kind} — {setup.rationale}",
        f"Entry zone: {setup.entry_low:.2f}-{setup.entry_high:.2f} {cur}; "
        f"stop {plan.stop:.2f}; target {plan.target:.2f}; R:R {plan.risk_reward:g}.",
        f"Sized plan: {plan.shares} shares ≈ {plan.cost:.2f} {cur} "
        f"({plan.pct_of_account:g}% of account), risking ~{plan.risk_amount:.2f} {cur}.",
        f"RSI: {technicals.rsi_14}; SMA50: {technicals.sma_50}; SMA200: {technicals.sma_200}.",
    ]
    if earnings.next_date is not None:
        lines.append(
            f"Next earnings: {earnings.next_date.isoformat()} (in {earnings.days_until} days)."
        )
    else:
        lines.append("Next earnings: unknown.")
    if news:
        lines.append("Recent news:")
        lines.extend(f"- {item.title}: {item.summary}".rstrip(": ") for item in news)
    else:
        lines.append("Recent news: none found.")
    return "\n".join(lines)


async def analyze(
    agent: Agent[None, SwingNote],
    quote: Quote,
    technicals: Technicals,
    setup: SwingSetup,
    plan: TradePlan,
    news: list[NewsItem],
    earnings: EarningsInfo,
) -> SwingNote:
    """Run the agent on a candidate's full state and return its structured note."""
    result = await agent.run(build_prompt(quote, technicals, setup, plan, news, earnings))
    return result.output
