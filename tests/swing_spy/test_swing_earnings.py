"""Tests for next-earnings extraction and the imminent-earnings flag."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd

from swing_spy.earnings import get_earnings
from swing_spy.models import EarningsInfo


def test_dict_calendar_with_date_list() -> None:
    soon = datetime.now(UTC).date() + timedelta(days=3)
    info = get_earnings("X", calendar_fn=lambda _t: {"Earnings Date": [soon]})
    assert info.next_date == soon
    assert info.days_until == 3
    assert info.is_imminent is True


def test_dataframe_calendar() -> None:
    far = date(2099, 1, 1)
    cal = pd.DataFrame({"Value": [far]}, index=["Earnings Date"])
    info = get_earnings("X", calendar_fn=lambda _t: cal)
    assert info.next_date == far
    assert info.is_imminent is False


def test_missing_or_failing_calendar_degrades_gracefully() -> None:
    assert get_earnings("X", calendar_fn=lambda _t: {}).next_date is None

    def _boom(_t: str) -> object:
        raise RuntimeError("yfinance hiccup")

    assert get_earnings("X", calendar_fn=_boom) == EarningsInfo()


def test_imminent_only_within_a_week() -> None:
    assert EarningsInfo(days_until=8).is_imminent is False
    assert EarningsInfo(days_until=0).is_imminent is True
    assert EarningsInfo(days_until=-1).is_imminent is False
