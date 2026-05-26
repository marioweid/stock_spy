"""LLM analysis + assembly of the final report, via Pydantic AI + Google AI Studio (Gemini)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from stock_spy.models import (
    EquityReport,
    Fundamentals,
    Holding,
    NewsItem,
    Portfolio,
    Quote,
    RiskAssessment,
    Scores,
    Signal,
    SwingSetup,
    Technicals,
    TradePlan,
)
from stock_spy.scoring import (
    assess_risk,
    composite,
    find_swing_setup,
    position_pct,
    score_fundamentals,
    score_technicals,
    size_position,
    verdict,
)

_INSTRUCTIONS = """
You are a patient stock-research assistant writing for someone BRAND NEW to investing.

Rules:
- Write in plain language. Whenever you use a financial term (P/E, margin, RSI, support, etc.),
  define it in a few words right there so a beginner understands.
- Ground every claim in the numbers you are given. Do not invent figures.
- Be honest about uncertainty and risks. This is informational only, never financial advice.

Given a ticker with its price move, fundamentals, technical indicators, and recent news,
produce structured output:
- summary: one short paragraph a beginner can follow — what this company is and what's going on.
- thesis: the core reason someone might own it.
- fundamental_view: what the financials say about business quality (explain the terms).
- valuation_view: is it cheap or expensive, and why.
- technical_view: what the price chart/indicators suggest (explain the terms).
- catalysts: upcoming events that could move it, each with a timeframe and positive/negative/mixed.
- risks: concrete things that could go wrong.
- bull_case / base_case / bear_case: short best / likely / worst scenarios.
- price_target: a rough fair value if you can estimate one, else null.
- conviction: 0.0-1.0, how sure you are.
- news_sentiment_score: 0-100 tone of the recent news (0 very negative, 50 neutral, 100 great).
- protection_note: if someone OWNS this, what should they watch for and worry about right now.
- opportunity_note: is now a reasonable swing-trade entry (days-to-weeks), and why or why not.
""".strip()


@dataclass(frozen=True)
class ReportBundle:
    """Everything the formatters need: market data, the LLM view, and the derived numbers."""

    quote: Quote
    fundamentals: Fundamentals
    technicals: Technicals
    report: EquityReport
    scores: Scores
    signal: Signal
    position_pct: float
    swing: SwingSetup
    trade_plan: TradePlan | None
    holding: Holding | None
    risk: RiskAssessment | None


def build_agent(api_key: str, model_name: str) -> Agent[None, EquityReport]:
    """Construct the analysis agent bound to Gemini via Google AI Studio.

    Args:
        api_key: Google AI Studio API key.
        model_name: Gemini model name, e.g. ``"gemini-2.5-flash"``.

    Returns:
        An agent whose output is a validated :class:`EquityReport`.
    """
    model = GoogleModel(model_name, provider=GoogleProvider(api_key=api_key))
    # ty does not yet narrow Agent's output type from output_type=; the cast is sound.
    return cast(
        "Agent[None, EquityReport]",
        Agent(model, output_type=EquityReport, instructions=_INSTRUCTIONS),
    )


def build_prompt(
    quote: Quote,
    fundamentals: Fundamentals,
    technicals: Technicals,
    news: list[NewsItem],
    *,
    holding: Holding | None = None,
    portfolio: Portfolio | None = None,
    notes: str | None = None,
) -> str:
    """Render the run input: the real numbers and the user's situation, for grounded analysis.

    Pure and side-effect free so it can be asserted on in tests.
    """
    lines = [
        f"Ticker: {quote.ticker}" + (f" ({notes})" if notes else ""),
        f"Price: {quote.price:.2f} {quote.currency} "
        f"({quote.pct_change:+.2f}% vs previous close {quote.previous_close:.2f})",
        "",
        "Fundamentals: " + _dump(fundamentals.model_dump()),
        "Technicals: " + _dump(technicals.model_dump()),
    ]
    if holding is not None:
        lines.append(
            f"User OWNS this: {holding.shares:g} shares at avg cost {holding.avg_cost:.2f}."
        )
    if portfolio is not None and portfolio.cash > 0:
        lines.append(f"User has {portfolio.cash:.0f} {portfolio.base_currency} cash to deploy.")
    if news:
        lines.append("Recent news:")
        lines.extend(f"- {item.title}: {item.summary}".rstrip(": ") for item in news)
    else:
        lines.append("Recent news: none found.")
    return "\n".join(lines)


def _dump(values: dict[str, object]) -> str:
    """Compact 'key=value' rendering that omits missing fields."""
    present = [f"{k}={_fmt(v)}" for k, v in values.items() if v is not None]
    return ", ".join(present) if present else "none available"


def _fmt(value: object) -> str:
    return f"{value:.4g}" if isinstance(value, float) else str(value)


async def analyze(
    agent: Agent[None, EquityReport],
    quote: Quote,
    fundamentals: Fundamentals,
    technicals: Technicals,
    news: list[NewsItem],
    *,
    holding: Holding | None = None,
    portfolio: Portfolio | None = None,
    notes: str | None = None,
) -> EquityReport:
    """Run the agent on a ticker's full state and return its structured view."""
    prompt = build_prompt(
        quote, fundamentals, technicals, news, holding=holding, portfolio=portfolio, notes=notes
    )
    result = await agent.run(prompt)
    return result.output


def assemble_report(
    quote: Quote,
    fundamentals: Fundamentals,
    technicals: Technicals,
    report: EquityReport,
    *,
    holding: Holding | None = None,
    portfolio: Portfolio | None = None,
) -> ReportBundle:
    """Combine market data + LLM view with the deterministic scoring and trade engines."""
    scores = composite(
        score_fundamentals(fundamentals), score_technicals(technicals), report.news_sentiment_score
    )
    swing = find_swing_setup(technicals)
    trade_plan = _plan_trade(swing, portfolio)
    risk = (
        assess_risk(quote, technicals, holding, report.news_sentiment_score)
        if holding is not None
        else None
    )
    return ReportBundle(
        quote=quote,
        fundamentals=fundamentals,
        technicals=technicals,
        report=report,
        scores=scores,
        signal=verdict(scores.overall),
        position_pct=position_pct(scores.overall, report.conviction),
        swing=swing,
        trade_plan=trade_plan,
        holding=holding,
        risk=risk,
    )


def _plan_trade(swing: SwingSetup, portfolio: Portfolio | None) -> TradePlan | None:
    """Size a swing trade from the user's cash, if a valid setup and cash both exist."""
    if portfolio is None or portfolio.cash <= 0 or not swing.is_setup:
        return None
    if swing.entry_high is None or swing.stop is None or swing.target_1 is None:
        return None
    return size_position(
        portfolio.cash,
        swing.entry_high,
        swing.stop,
        swing.target_1,
        risk_per_trade_pct=portfolio.risk_per_trade_pct,
        max_position_pct=portfolio.max_position_pct,
    )
