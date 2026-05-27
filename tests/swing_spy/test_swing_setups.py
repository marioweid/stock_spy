"""Tests for deterministic swing-setup detection."""

from __future__ import annotations

from spy_core.models import Technicals
from swing_spy.setups import find_swing_setup


def test_pullback_in_uptrend_is_a_setup() -> None:
    t = Technicals(
        last_close=100.0,
        sma_50=99.0,
        sma_200=90.0,
        rsi_14=50.0,
        support=98.0,
        resistance=110.0,
        atr_14=3.0,
    )

    setup = find_swing_setup(t)

    assert setup.is_setup is True
    assert setup.kind == "pullback"
    assert setup.stop == 95.0  # support - atr
    assert setup.target_1 == 110.0
    assert setup.risk_reward == 2.0  # (110-100)/(100-95)


def test_oversold_in_uptrend_is_a_bounce_setup() -> None:
    t = Technicals(
        last_close=102.0,
        sma_50=108.0,
        sma_200=90.0,
        rsi_14=30.0,
        support=100.0,
        resistance=120.0,
        atr_14=2.0,
    )
    setup = find_swing_setup(t)
    assert setup.is_setup is True
    assert setup.kind == "oversold_bounce"


def test_no_uptrend_is_not_a_setup() -> None:
    t = Technicals(last_close=85.0, sma_200=100.0, support=80.0, resistance=110.0, atr_14=3.0)
    assert find_swing_setup(t).is_setup is False


def test_missing_data_is_not_a_setup() -> None:
    assert find_swing_setup(Technicals(last_close=100.0)).is_setup is False


def test_extended_price_with_no_pullback_is_not_a_setup() -> None:
    t = Technicals(
        last_close=130.0,
        sma_50=110.0,
        sma_200=90.0,
        rsi_14=60.0,
        support=100.0,
        resistance=135.0,
        atr_14=3.0,
    )
    assert find_swing_setup(t).is_setup is False  # in uptrend but no clean entry
