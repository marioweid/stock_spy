"""Guard that every metric the report renders has a beginner explanation."""

from __future__ import annotations

from datetime import UTC, datetime

from signal_spy.analysis import assemble_report
from signal_spy.glossary import GLOSSARY
from signal_spy.models import EquityReport, Fundamentals, Holding
from signal_spy.report import _fundamental_rows, _key_rows, _technical_rows, _terms_used
from spy_core.models import Quote, Technicals


def _full_bundle():
    quote = Quote(
        ticker="AAPL", price=100.0, previous_close=100.0, currency="USD", as_of=datetime.now(UTC)
    )
    fundamentals = Fundamentals(
        trailing_pe=30.0,
        forward_pe=28.0,
        peg_ratio=2.0,
        price_to_book=10.0,
        profit_margin=0.25,
        gross_margin=0.46,
        revenue_growth=0.1,
        earnings_growth=0.2,
        return_on_equity=0.5,
        debt_to_equity=80.0,
        beta=1.1,
        market_cap=4.5e12,
        dividend_yield=0.004,
        free_cashflow=1e11,
        target_mean_price=320.0,
        recommendation_key="buy",
    )
    technicals = Technicals(
        last_close=100.0,
        sma_50=99.0,
        sma_200=90.0,
        rsi_14=55.0,
        macd=1.0,
        macd_signal=0.5,
        atr_14=3.0,
        support=98.0,
        resistance=110.0,
        recent_swing_low=97.0,
        pct_from_52w_high=-5.0,
        volatility_30d=1.5,
    )
    report = EquityReport(
        summary="s",
        thesis="t",
        fundamental_view="f",
        valuation_view="v",
        technical_view="te",
        bull_case="b",
        base_case="ba",
        bear_case="be",
        conviction=0.7,
        news_sentiment_score=70.0,
        protection_note="p",
    )
    return assemble_report(
        quote,
        fundamentals,
        technicals,
        report,
        holding=Holding(ticker="AAPL", shares=10, avg_cost=80.0),
    )


def test_every_rendered_metric_term_is_in_glossary() -> None:
    bundle = _full_bundle()
    rows = _fundamental_rows(bundle) + _technical_rows(bundle) + _key_rows(bundle)
    terms = {term for _, _, term in rows}

    missing = terms - set(GLOSSARY)
    assert missing == set(), f"glossary missing entries for: {missing}"


def test_terms_used_are_all_defined() -> None:
    missing = set(_terms_used(_full_bundle())) - set(GLOSSARY)
    assert missing == set()
