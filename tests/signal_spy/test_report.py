"""Tests for beginner-facing report formatting."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from signal_spy.analysis import ReportBundle, assemble_report
from signal_spy.models import EquityReport, Fundamentals, Holding
from signal_spy.report import (
    format_protection_alert,
    format_summary,
    render_markdown,
)
from spy_core.models import Quote, Technicals


def _report(**over: object) -> EquityReport:
    defaults: dict[str, Any] = {
        "summary": "Apple makes phones.",
        "thesis": "Strong brand.",
        "fundamental_view": "Profitable.",
        "valuation_view": "Pricey.",
        "technical_view": "Uptrend.",
        "risks": ["Demand could slow", "Regulation"],
        "bull_case": "Up.",
        "base_case": "Flat.",
        "bear_case": "Down.",
        "price_target": 320.0,
        "conviction": 0.8,
        "news_sentiment_score": 70.0,
        "protection_note": "Watch the 200-day line.",
    }
    defaults.update(over)
    return EquityReport(**defaults)


def _bundle(*, price: float, holding: Holding | None) -> ReportBundle:
    quote = Quote(
        ticker="AAPL", price=price, previous_close=100.0, currency="USD", as_of=datetime.now(UTC)
    )
    technicals = Technicals(
        last_close=price,
        sma_50=99.0,
        sma_200=90.0,
        rsi_14=50.0,
        macd=1.0,
        macd_signal=0.5,
        atr_14=3.0,
        support=98.0,
        resistance=110.0,
        recent_swing_low=97.0,
        pct_from_52w_high=-5.0,
        volatility_30d=1.5,
    )
    fundamentals = Fundamentals(
        trailing_pe=30.0,
        profit_margin=0.25,
        target_mean_price=320.0,
        market_cap=4.5e12,
        recommendation_key="buy",
    )
    return assemble_report(quote, fundamentals, technicals, _report(), holding=holding)


def test_summary_has_score_verdict_and_metrics() -> None:
    msg = format_summary(_bundle(price=100.0, holding=None))

    assert "<b>AAPL</b>" in msg
    assert "/100" in msg
    assert "P/E" in msg
    assert "not financial advice" in msg


def test_protection_alert_quantifies_money_at_risk() -> None:
    holding = Holding(ticker="AAPL", shares=10, avg_cost=120.0)
    msg = format_protection_alert(_bundle(price=90.0, holding=holding))

    assert "HEADS-UP" in msg
    assert "you own 10" in msg
    assert "-100.00 USD" in msg  # 10 * (90 - 100) today
    assert "Risk:" in msg


def test_protection_alert_falls_back_without_holding() -> None:
    msg = format_protection_alert(_bundle(price=100.0, holding=None))
    assert "/100" in msg  # falls back to summary


def test_markdown_has_sections_and_glossary() -> None:
    md = render_markdown(
        _bundle(price=100.0, holding=Holding(ticker="AAPL", shares=10, avg_cost=80.0))
    )

    for heading in (
        "# AAPL",
        "## Executive summary",
        "## Your position & risk",
        "## Fundamentals",
        "## Technicals",
        "## Glossary",
    ):
        assert heading in md
    assert "**P/E:**" in md
    assert "Average True Range" in md  # ATR glossary text rendered
