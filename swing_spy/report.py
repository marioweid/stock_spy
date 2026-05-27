"""Render a swing candidate as a Telegram alert (HTML) and a full markdown report.

Each metric is paired with a one-line gloss from :mod:`swing_spy.glossary` so a newcomer can
follow what the numbers mean. Telegram bodies use HTML; the attached file is markdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

from spy_core.models import Quote, Technicals
from swing_spy.glossary import GLOSSARY, explain
from swing_spy.models import EarningsInfo, SwingNote, SwingSetup, TradePlan

_DISCLAIMER = "Not financial advice. Always set your stop before you buy."


def candidate_signature(quote: Quote, plan: TradePlan) -> str:
    """Stable identity for dedup: trade date plus the rounded entry and stop."""
    return f"{quote.as_of.date().isoformat()}:{plan.entry}:{plan.stop}"


@dataclass(frozen=True)
class Candidate:
    """A fully evaluated swing candidate: market data, the setup, the sized plan, and context."""

    quote: Quote
    technicals: Technicals
    setup: SwingSetup
    plan: TradePlan
    note: SwingNote
    earnings: EarningsInfo

    def signature(self) -> str:
        """Stable identity for dedup: trade date plus the rounded entry and stop."""
        return candidate_signature(self.quote, self.plan)


def _earnings_warning(earnings: EarningsInfo) -> str | None:
    """A one-line caution if earnings land within the next week, else ``None``."""
    if not earnings.is_imminent:
        return None
    return (
        f"Earnings in {earnings.days_until} day(s) "
        f"({earnings.next_date.isoformat() if earnings.next_date else '?'}) — "
        "holding a swing trade through earnings is risky."
    )


def format_candidate_alert(candidate: Candidate) -> str:
    """Render a full swing trade plan for one candidate (Telegram HTML)."""
    q, setup, plan = candidate.quote, candidate.setup, candidate.plan
    cur = escape(q.currency)
    lines = [
        f"\U0001f4a1 <b>SWING IDEA: {escape(q.ticker)}</b>",
        escape(setup.rationale),
        "",
        "<b>Trade plan (sized for ~1% account risk)</b>",
        f"• Buy zone: {setup.entry_low:.2f} to {setup.entry_high:.2f} {cur}",
        f"• Stop-loss: {plan.stop:.2f} {cur} (exit here to cap the loss)",
        f"• Target: {plan.target:.2f} {cur}",
        f"• Risk/Reward: {plan.risk_reward:g} (aim to make {plan.risk_reward:g}x the risk)",
        f"• Buy: {plan.shares} shares ≈ {plan.cost:,.2f} {cur} "
        f"({plan.pct_of_account:g}% of account)",
        f"• If stopped out: ≈ {plan.risk_amount:,.2f} {cur} loss; "
        f"at target: ≈ {plan.reward_amount:,.2f} {cur} gain.",
    ]
    warning = _earnings_warning(candidate.earnings)
    if warning is not None:
        lines += ["", f"⚠️ {escape(warning)}"]
    lines += ["", escape(candidate.note.rationale), "", _DISCLAIMER]
    return "\n".join(lines)


def render_markdown(candidate: Candidate) -> str:
    """Render the full candidate report as a markdown document, glossary included."""
    q, setup, plan = candidate.quote, candidate.setup, candidate.plan
    cur = q.currency
    out = [
        f"# {q.ticker} — Swing Candidate",
        f"*Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC}. Not financial advice.*",
        "",
        f"**{setup.kind.replace('_', ' ').title()} setup.** {setup.rationale}",
        f"Price {q.price:.2f} {cur} ({q.pct_change:+.2f}% today).",
        "",
        "## Trade plan (sized for ~1% account risk)",
        f"- Buy zone: {setup.entry_low:.2f} to {setup.entry_high:.2f} {cur}",
        f"- Stop-loss: {plan.stop:.2f} {cur}",
        f"- Target: {plan.target:.2f} {cur} (risk/reward {plan.risk_reward:g})",
        f"- Buy: {plan.shares} shares ≈ {plan.cost:,.2f} {cur} ({plan.pct_of_account:g}% of "
        f"account); risk ≈ {plan.risk_amount:,.2f} {cur}",
        f"- Reward at target ≈ {plan.reward_amount:,.2f} {cur}.",
    ]
    warning = _earnings_warning(candidate.earnings)
    out += ["", "## Earnings", f"- {warning}" if warning else "- No imminent earnings flagged."]
    out += ["", "## Technicals", _metric_list(_technical_rows(candidate))]
    out += ["", "## What the analysis says", candidate.note.rationale]
    glossary = [f"- **{term}** — {GLOSSARY[term]}" for term in _terms_used(candidate)]
    out += ["", "## Glossary", *glossary]
    return "\n".join(out)


def _technical_rows(candidate: Candidate) -> list[tuple[str, str, str]]:
    """Available technical metrics for the markdown report: (label, value, glossary key)."""
    t, cur = candidate.technicals, candidate.quote.currency
    candidates: list[tuple[str, float | str | None, str]] = [
        ("SMA 50", _money(t.sma_50, cur), "SMA"),
        ("SMA 200", _money(t.sma_200, cur), "SMA"),
        ("RSI", t.rsi_14, "RSI"),
        ("ATR", _money(t.atr_14, cur), "ATR"),
        ("Support", _money(t.support, cur), "Support"),
        ("Resistance", _money(t.resistance, cur), "Resistance"),
    ]
    rows: list[tuple[str, str, str]] = []
    for label, value, term in candidates:
        if value is None:
            continue
        text = f"{value:.2f}" if isinstance(value, float) else str(value)
        rows.append((label, text, term))
    return rows


def _metric_list(rows: list[tuple[str, str, str]]) -> str:
    """Render metric rows as markdown bullets with their glossary explanation."""
    if not rows:
        return "_No data available._"
    return "\n".join(f"- **{label}:** {value} — {explain(term)}" for label, value, term in rows)


def _terms_used(candidate: Candidate) -> list[str]:
    """Glossary terms referenced in the report, plus the always-shown swing concepts."""
    base = [
        "Swing trade",
        "Entry zone",
        "Stop-loss",
        "Target",
        "Risk/Reward",
        "Position size",
    ]
    if candidate.setup.kind == "pullback":
        base.append("Pullback")
    metric_terms = [term for _, _, term in _technical_rows(candidate)]
    seen: dict[str, None] = {}
    for term in base + metric_terms:
        if term in GLOSSARY:
            seen.setdefault(term, None)
    return list(seen)


def _money(value: float | None, currency: str) -> str | None:
    return None if value is None else f"{value:,.2f} {currency}"
