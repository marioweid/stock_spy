"""Tests for candidate alert and markdown rendering."""

from __future__ import annotations

from datetime import UTC, date, datetime

from spy_core.models import Quote, Technicals
from swing_spy.glossary import GLOSSARY
from swing_spy.models import EarningsInfo, SwingNote, SwingSetup, TradePlan
from swing_spy.report import (
    Candidate,
    candidate_signature,
    format_candidate_alert,
    render_markdown,
)


def _candidate(*, earnings: EarningsInfo | None = None) -> Candidate:
    quote = Quote(
        ticker="MUV2.DE",
        price=468.0,
        previous_close=465.0,
        currency="EUR",
        as_of=datetime(2026, 5, 27, tzinfo=UTC),
    )
    technicals = Technicals(
        last_close=468.0,
        sma_50=470.0,
        sma_200=450.0,
        rsi_14=45.0,
        atr_14=8.0,
        support=461.0,
        resistance=492.0,
    )
    setup = SwingSetup(
        is_setup=True,
        kind="pullback",
        entry_low=461.0,
        entry_high=468.0,
        stop=458.0,
        target_1=492.0,
        target_2=508.0,
        risk_reward=2.4,
        rationale="Pulled back to support.",
    )
    plan = TradePlan(
        shares=10,
        entry=468.0,
        stop=458.0,
        target=492.0,
        cost=4680.0,
        risk_amount=100.0,
        reward_amount=240.0,
        risk_reward=2.4,
        pct_of_account=46.8,
    )
    note = SwingNote(
        rationale="Bounce off support looks plausible.", news_sentiment_score=60.0, conviction=0.6
    )
    return Candidate(
        quote=quote,
        technicals=technicals,
        setup=setup,
        plan=plan,
        note=note,
        earnings=earnings or EarningsInfo(),
    )


def test_alert_shows_plan_numbers() -> None:
    msg = format_candidate_alert(_candidate())
    assert "SWING IDEA: MUV2.DE" in msg
    assert "Buy zone: 461.00 to 468.00 EUR" in msg
    assert "10 shares" in msg
    assert "Stop-loss: 458.00" in msg
    assert "Target: 492.00" in msg
    assert "Not financial advice" in msg


def test_alert_adds_earnings_warning_when_imminent() -> None:
    soon = _candidate(earnings=EarningsInfo(next_date=date(2026, 5, 30), days_until=3))
    quiet = _candidate(earnings=EarningsInfo(next_date=date(2099, 1, 1), days_until=900))
    assert "⚠️" in format_candidate_alert(soon)
    assert "Earnings in 3 day" in format_candidate_alert(soon)
    assert "⚠️" not in format_candidate_alert(quiet)


def test_markdown_has_sections_and_glossary_terms_defined() -> None:
    md = render_markdown(_candidate())
    for heading in ("# MUV2.DE", "## Trade plan", "## Technicals", "## Glossary"):
        assert heading in md
    # Every glossary term the report references must have a definition.
    referenced = [line for line in md.splitlines() if line.startswith("- **")]
    assert referenced  # the glossary section rendered some terms


def test_signature_is_date_entry_stop() -> None:
    assert candidate_signature(_candidate().quote, _candidate().plan) == "2026-05-27:468.0:458.0"


def test_every_glossary_term_used_is_defined() -> None:
    from swing_spy.report import _terms_used

    missing = set(_terms_used(_candidate())) - set(GLOSSARY)
    assert missing == set()
