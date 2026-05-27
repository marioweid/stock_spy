"""Beginner-friendly rendering of a report: Telegram summaries/alerts and a full markdown file.

Every metric shown is paired with a one-line explanation from :mod:`signal_spy.glossary`, so a
newcomer can follow what each number means. Telegram bodies use HTML; the file is markdown.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from signal_spy.analysis import ReportBundle
from signal_spy.glossary import GLOSSARY, explain
from signal_spy.models import RiskLevel, Signal

_DISCLAIMER = "Informational only — not financial advice."
_SIGNAL_LABEL: dict[Signal, str] = {
    "buy": "\U0001f7e2 BUY",
    "hold": "\U0001f7e1 HOLD",
    "sell": "\U0001f534 SELL",
}
_RISK_LABEL: dict[RiskLevel, str] = {
    "low": "\U0001f7e2 LOW",
    "elevated": "\U0001f7e1 ELEVATED",
    "high": "\U0001f7e0 HIGH",
    "critical": "\U0001f534 CRITICAL",
}


def format_summary(bundle: ReportBundle) -> str:
    """Render the scored quality summary for a Telegram message (HTML)."""
    q, s, r = bundle.quote, bundle.scores, bundle.report
    cur = q.currency
    lines = [
        f"\U0001f4ca <b>{escape(q.ticker)}</b> — Score <b>{s.overall:.0f}/100</b> "
        f"({_SIGNAL_LABEL[bundle.signal]})",
        f"{q.price:.2f} {escape(cur)} ({q.pct_change:+.2f}% today)",
        "",
        f"Fundamentals {s.fundamental:.0f} · Technicals {s.technical:.0f} "
        f"· News {s.sentiment:.0f}  (out of 100)",
        "",
        "<b>Key numbers</b>",
    ]
    lines.extend(f"• {label}: {value}" for label, value, _ in _key_rows(bundle))
    lines += ["", "<b>What it means</b>", escape(r.summary)]
    if r.price_target is not None:
        lines.append(f"\n\U0001f3af Rough fair value: ~{r.price_target:.2f} {escape(cur)}")
    lines.append(f"Suggested size if buying: {bundle.position_pct:g}% of your capital.")
    lines += _bullet_block("Top risks", r.risks[:2])
    lines.append(f"\n{_DISCLAIMER}")
    return "\n".join(lines)


def format_protection_alert(bundle: ReportBundle) -> str:
    """Render a plain-language protection heads-up for a holding (HTML)."""
    q, risk, holding = bundle.quote, bundle.risk, bundle.holding
    if risk is None or holding is None:
        return format_summary(bundle)
    cur = q.currency
    lines = [
        f"⚠️ <b>HEADS-UP: {escape(q.ticker)}</b> (you own {holding.shares:g})",
        f"Risk: {_RISK_LABEL[risk.risk_level]}",
        "",
        f"Today: {q.pct_change:+.2f}% → {risk.todays_change:+,.2f} {escape(cur)} on your shares.",
        f"Position value: {risk.position_value:,.2f} {escape(cur)} "
        f"(unrealized {risk.unrealized_pl:+,.2f} {escape(cur)}, "
        f"{risk.unrealized_pl_pct:+.1f}% vs what you paid).",
    ]
    if risk.downside_to_support is not None:
        lines.append(
            f"If it slid to support, that's about {-risk.downside_to_support:,.2f} {escape(cur)} "
            "more."
        )
    lines += _bullet_block("Why this matters", risk.triggers)
    lines += ["", escape(bundle.report.protection_note), "", _DISCLAIMER]
    return "\n".join(lines)


def render_markdown(bundle: ReportBundle) -> str:
    """Render the full multi-section report as a markdown document, glossary included."""
    q, s, r = bundle.quote, bundle.scores, bundle.report
    cur = q.currency
    out = [
        f"# {q.ticker} — Equity Report",
        f"*Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC}. Informational only — "
        "not financial advice.*",
        "",
        f"**Verdict: {bundle.signal.upper()} — Score {s.overall:.0f}/100**  "
        f"(Fundamentals {s.fundamental:.0f} · Technicals {s.technical:.0f} "
        f"· News {s.sentiment:.0f})",
        f"Price {q.price:.2f} {cur} ({q.pct_change:+.2f}% today). "
        f"Suggested position size: {bundle.position_pct:g}% of capital.",
        "",
        "## Executive summary",
        r.summary,
    ]
    out += _markdown_position(bundle, cur)
    out += ["", "## Investment thesis", r.thesis]
    out += ["", "## Fundamentals", r.fundamental_view, "", _metric_list(_fundamental_rows(bundle))]
    out += ["", "## Valuation", r.valuation_view]
    out += ["", "## Technicals", r.technical_view, "", _metric_list(_technical_rows(bundle))]
    catalysts = [f"- **{c.title}** ({c.timeframe}) — {c.impact}" for c in r.catalysts]
    out += ["", "## Catalysts", *(catalysts or ["- None noted."])]
    out += ["", "## Risks", *([f"- {risk}" for risk in r.risks] or ["- None noted."])]
    out += [
        "",
        "## Scenarios",
        f"- **Bull:** {r.bull_case}",
        f"- **Base:** {r.base_case}",
        f"- **Bear:** {r.bear_case}",
    ]
    glossary = [f"- **{term}** — {GLOSSARY[term]}" for term in _terms_used(bundle)]
    out += ["", "## Glossary", *glossary]
    return "\n".join(out)


# --- shared helpers ----------------------------------------------------------


def _bullet_block(heading: str, items: list[str]) -> list[str]:
    """An HTML bullet block, or empty if there are no items."""
    if not items:
        return []
    return ["", f"<b>{heading}</b>", *[f"• {escape(item)}" for item in items]]


def _key_rows(bundle: ReportBundle) -> list[tuple[str, str, str]]:
    """The handful of metrics shown in the Telegram summary: (label, value, glossary key)."""
    f, t, cur = bundle.fundamentals, bundle.technicals, bundle.quote.currency
    rows: list[tuple[str, str, str]] = []
    if f.trailing_pe is not None:
        rows.append(("P/E", f"{f.trailing_pe:.1f}", "P/E"))
    if f.profit_margin is not None:
        rows.append(("Profit margin", f"{f.profit_margin * 100:.0f}%", "Profit margin"))
    if f.target_mean_price is not None:
        rows.append(("Analyst target", f"{f.target_mean_price:.2f} {cur}", "Analyst target"))
    if t.rsi_14 is not None:
        rows.append(("RSI", f"{t.rsi_14:.0f}", "RSI"))
    return rows


def _fundamental_rows(bundle: ReportBundle) -> list[tuple[str, str, str]]:
    """All available fundamental metrics for the markdown report."""
    f, cur = bundle.fundamentals, bundle.quote.currency
    candidates: list[tuple[str, float | str | None, str]] = [
        ("P/E", f.trailing_pe, "P/E"),
        ("Forward P/E", f.forward_pe, "Forward P/E"),
        ("PEG", f.peg_ratio, "PEG"),
        ("P/B", f.price_to_book, "P/B"),
        ("Profit margin", _pct(f.profit_margin), "Profit margin"),
        ("Gross margin", _pct(f.gross_margin), "Gross margin"),
        ("Revenue growth", _pct(f.revenue_growth), "Revenue growth"),
        ("Earnings growth", _pct(f.earnings_growth), "Earnings growth"),
        ("ROE", _pct(f.return_on_equity), "ROE"),
        ("Debt/Equity", f.debt_to_equity, "Debt/Equity"),
        ("Beta", f.beta, "Beta"),
        ("Market cap", _big(f.market_cap, cur), "Market cap"),
        ("Dividend yield", _pct(f.dividend_yield), "Dividend yield"),
        ("Free cash flow", _big(f.free_cashflow, cur), "Free cash flow"),
        ("Analyst target", _money(f.target_mean_price, cur), "Analyst target"),
    ]
    return _present_rows(candidates)


def _technical_rows(bundle: ReportBundle) -> list[tuple[str, str, str]]:
    """All available technical metrics for the markdown report."""
    t, cur = bundle.technicals, bundle.quote.currency
    candidates: list[tuple[str, float | str | None, str]] = [
        ("SMA 50", _money(t.sma_50, cur), "SMA"),
        ("SMA 200", _money(t.sma_200, cur), "SMA"),
        ("RSI", t.rsi_14, "RSI"),
        ("MACD", t.macd, "MACD"),
        ("ATR", _money(t.atr_14, cur), "ATR"),
        ("Support", _money(t.support, cur), "Support"),
        ("Resistance", _money(t.resistance, cur), "Resistance"),
        ("From 52w high", _pct_points(t.pct_from_52w_high), "52-week range"),
        ("Volatility", _pct_points(t.volatility_30d), "Volatility"),
    ]
    return _present_rows(candidates)


def _present_rows(
    candidates: list[tuple[str, float | str | None, str]],
) -> list[tuple[str, str, str]]:
    """Keep only rows whose value is present, formatting floats to 2 decimals."""
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


def _markdown_position(bundle: ReportBundle, cur: str) -> list[str]:
    """The 'Your position & risk' section, only when the user holds the stock."""
    risk, holding = bundle.risk, bundle.holding
    if risk is None or holding is None:
        return []
    return [
        "",
        "## Your position & risk",
        f"- You own **{holding.shares:g} shares** at avg cost {holding.avg_cost:.2f} {cur}.",
        f"- Position value: {risk.position_value:,.2f} {cur} "
        f"(unrealized {risk.unrealized_pl:+,.2f} {cur}, {risk.unrealized_pl_pct:+.1f}%).",
        f"- Today: {risk.todays_change:+,.2f} {cur}.",
        f"- Risk level: **{risk.risk_level.upper()}**."
        + ("" if not risk.triggers else " " + " ".join(risk.triggers)),
        "",
        bundle.report.protection_note,
    ]


def _terms_used(bundle: ReportBundle) -> list[str]:
    """Glossary terms referenced anywhere in the report, plus the always-shown concepts."""
    base = [
        "Composite score",
        "Signal",
        "Conviction",
        "Position size",
        "Risk level",
        "Unrealized P/L",
    ]
    metric_terms = [term for _, _, term in _fundamental_rows(bundle) + _technical_rows(bundle)]
    seen: dict[str, None] = {}
    for term in base + metric_terms:
        if term in GLOSSARY:
            seen.setdefault(term, None)
    return list(seen)


def _money(value: float | None, currency: str) -> str | None:
    return None if value is None else f"{value:,.2f} {currency}"


def _pct(fraction: float | None) -> str | None:
    """Format a fraction (0.27) as a percent string ('27.0%')."""
    return None if fraction is None else f"{fraction * 100:.1f}%"


def _pct_points(value: float | None) -> str | None:
    """Format an already-percent value ('-3.2%')."""
    return None if value is None else f"{value:.1f}%"


def _big(value: float | None, currency: str) -> str | None:
    """Abbreviate large currency amounts (e.g. '4.53T USD')."""
    if value is None:
        return None
    for scale, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= scale:
            return f"{value / scale:.2f}{suffix} {currency}"
    return f"{value:,.0f} {currency}"
