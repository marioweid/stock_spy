"""Tests for converting scanner candidates into dashboard snapshots."""

from __future__ import annotations

from datetime import UTC, date, datetime

from spy_core.models import Quote, Technicals
from swing_spy.dashboard_candidates import candidate_to_snapshot
from swing_spy.models import EarningsInfo, SwingNote, SwingSetup, TradePlan
from swing_spy.report import Candidate


def test_candidate_to_snapshot_preserves_trade_plan() -> None:
    snapshot = candidate_to_snapshot(_candidate())

    assert snapshot.ticker == "MUV2.DE"
    assert snapshot.entry == 468.0
    assert snapshot.stop == 458.0
    assert snapshot.target == 492.0
    assert snapshot.risk_reward == 2.4
    assert snapshot.earnings_warning == "Earnings in 3 day(s) on 2026-05-31."


def _candidate() -> Candidate:
    return Candidate(
        quote=Quote(
            ticker="MUV2.DE",
            price=468.0,
            previous_close=465.0,
            currency="EUR",
            as_of=datetime(2026, 5, 28, tzinfo=UTC),
        ),
        technicals=Technicals(last_close=468.0),
        setup=SwingSetup(
            is_setup=True,
            kind="pullback",
            entry_low=461.0,
            entry_high=468.0,
            stop=458.0,
            target_1=492.0,
            target_2=508.0,
            risk_reward=2.4,
            rationale="Pulled back toward support.",
        ),
        plan=TradePlan(
            shares=10,
            entry=468.0,
            stop=458.0,
            target=492.0,
            cost=4680.0,
            risk_amount=100.0,
            reward_amount=240.0,
            risk_reward=2.4,
            pct_of_account=46.8,
        ),
        note=SwingNote(rationale="Looks plausible.", news_sentiment_score=60.0, conviction=0.6),
        earnings=EarningsInfo(next_date=date(2026, 5, 31), days_until=3),
    )
