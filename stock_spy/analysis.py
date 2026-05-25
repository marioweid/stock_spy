"""LLM analysis of a ticker's situation, via Pydantic AI + Google AI Studio (Gemini)."""

from __future__ import annotations

from typing import cast

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from stock_spy.models import Analysis, NewsItem, Quote

_INSTRUCTIONS = """
You are a stock-monitoring assistant for a long-term retail investor.

Given a ticker, its recent price move, and recent news headlines, assess the situation
and produce structured output:
- signal: "buy", "hold", or "sell".
- confidence: 0.0-1.0, how sure you are of the signal.
- summary: two or three sentences on what is happening.
- pros: concrete reasons supporting holding or buying.
- cons: concrete risks or reasons for caution.
- cause: the single news item or event most likely driving any price move, or null.
- significant: true ONLY if a long-term investor would want a notification right now
  (material news or a notable move); false for routine noise.

Your output is informational and must not be presented as financial advice.
""".strip()


def build_agent(api_key: str, model_name: str) -> Agent[None, Analysis]:
    """Construct the analysis agent bound to Gemini via Google AI Studio.

    Args:
        api_key: Google AI Studio API key.
        model_name: Gemini model name, e.g. ``"gemini-2.5-flash"``.

    Returns:
        An agent whose output is a validated :class:`Analysis`.
    """
    model = GoogleModel(model_name, provider=GoogleProvider(api_key=api_key))
    # ty does not yet narrow Agent's output type from output_type=; the cast is sound.
    return cast(
        "Agent[None, Analysis]",
        Agent(model, output_type=Analysis, instructions=_INSTRUCTIONS),
    )


def build_prompt(quote: Quote, news: list[NewsItem], notes: str | None) -> str:
    """Render the run input describing the ticker's current state.

    Pure and side-effect free so it can be asserted on in tests.
    """
    lines = [
        f"Ticker: {quote.ticker}" + (f" ({notes})" if notes else ""),
        f"Price: {quote.price:.2f} {quote.currency} "
        f"({quote.pct_change:+.2f}% vs previous close {quote.previous_close:.2f})",
    ]
    if news:
        lines.append("Recent news:")
        lines.extend(f"- {item.title}: {item.summary}".rstrip(": ") for item in news)
    else:
        lines.append("Recent news: none found.")
    return "\n".join(lines)


async def analyze(
    agent: Agent[None, Analysis],
    quote: Quote,
    news: list[NewsItem],
    notes: str | None = None,
) -> Analysis:
    """Run the agent on a ticker's state and return its structured verdict."""
    result = await agent.run(build_prompt(quote, news, notes))
    return result.output
