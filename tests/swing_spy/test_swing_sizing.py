"""Tests for 1%-risk position sizing."""

from __future__ import annotations

from swing_spy.sizing import size_position


def test_munich_re_example_sizes_to_one_percent_risk() -> None:
    # swing_buddy_example.md: 10000 account, entry 468, stop 458, target 492 -> 10 shares, 1% risk.
    plan = size_position(
        10_000.0, 468.0, 458.0, 492.0, risk_per_trade_pct=1.0, max_position_pct=50.0
    )
    assert plan is not None
    assert plan.shares == 10
    assert plan.risk_amount == 100.0  # exactly 1% of the account
    assert plan.reward_amount == 240.0
    assert plan.risk_reward == 2.4
    assert plan.pct_of_account == 46.8


def test_exposure_cap_binds_before_risk_cap() -> None:
    # Tight stop (1 unit) would let the risk cap buy 100 shares; the 20% exposure cap limits it.
    plan = size_position(
        10_000.0, 100.0, 99.0, 110.0, risk_per_trade_pct=1.0, max_position_pct=20.0
    )
    assert plan is not None
    assert plan.shares == 20  # 20% / 100 = 20 shares, below the 100 the risk cap would allow
    assert plan.pct_of_account == 20.0


def test_rejects_zero_or_negative_risk() -> None:
    assert (
        size_position(10_000.0, 100.0, 100.0, 110.0, risk_per_trade_pct=1.0, max_position_pct=50.0)
        is None
    )


def test_rejects_when_unaffordable() -> None:
    assert (
        size_position(10.0, 100.0, 95.0, 110.0, risk_per_trade_pct=1.0, max_position_pct=50.0)
        is None
    )
