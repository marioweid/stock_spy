"""Convert scanner candidates into persisted dashboard snapshots."""

from __future__ import annotations

from swing_spy.report import Candidate
from swing_spy.trade_models import CandidateSnapshot


def candidate_to_snapshot(candidate: Candidate) -> CandidateSnapshot:
    """Return a dashboard snapshot from a fully built scanner candidate."""
    earnings_warning = None
    if candidate.earnings.is_imminent:
        next_date = (
            "unknown"
            if candidate.earnings.next_date is None
            else candidate.earnings.next_date.isoformat()
        )
        earnings_warning = f"Earnings in {candidate.earnings.days_until} day(s) on {next_date}."
    return CandidateSnapshot(
        ticker=candidate.quote.ticker,
        signature=candidate.signature(),
        setup_kind=candidate.setup.kind,
        currency=candidate.quote.currency,
        entry=candidate.plan.entry,
        stop=candidate.plan.stop,
        target=candidate.plan.target,
        risk_reward=candidate.plan.risk_reward,
        shares=candidate.plan.shares,
        cost=candidate.plan.cost,
        risk_amount=candidate.plan.risk_amount,
        reward_amount=candidate.plan.reward_amount,
        rationale=candidate.setup.rationale,
        earnings_warning=earnings_warning,
        created_at=candidate.quote.as_of,
    )
