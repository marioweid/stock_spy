"""Risk-based position sizing: how many shares to buy so a stop-out loses ~1% of the account."""

from __future__ import annotations

import math

from swing_spy.models import TradePlan


def size_position(
    account_balance: float,
    entry: float,
    stop: float,
    target: float,
    *,
    risk_per_trade_pct: float,
    max_position_pct: float,
) -> TradePlan | None:
    """Size a swing trade so a stop-out loses at most ``risk_per_trade_pct`` of the account.

    The share count is the smaller of two limits: the risk limit (so ``entry - stop`` times the
    quantity stays within the allowed loss) and the exposure limit (so the position costs no
    more than ``max_position_pct`` of the account). Both guard against over-sizing — a tight stop
    would otherwise let the risk limit alone buy a huge, concentrated position.

    Args:
        account_balance: Capital the percentages are computed against.
        entry: Planned entry price.
        stop: Planned stop-loss price (must be below ``entry``).
        target: Planned take-profit price.
        risk_per_trade_pct: Percent of the account risked if the stop is hit.
        max_position_pct: Cap on the percent of the account this position may cost.

    Returns:
        A sized :class:`TradePlan`, or ``None`` when no affordable, positive-risk position exists.
    """
    risk_per_share = entry - stop
    if risk_per_share <= 0 or account_balance <= 0 or entry <= 0:
        return None
    shares_by_risk = math.floor((account_balance * risk_per_trade_pct / 100.0) / risk_per_share)
    shares_by_cost = math.floor((account_balance * max_position_pct / 100.0) / entry)
    shares = min(shares_by_risk, shares_by_cost)
    if shares <= 0:
        return None
    cost = shares * entry
    return TradePlan(
        shares=shares,
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        cost=round(cost, 2),
        risk_amount=round(shares * risk_per_share, 2),
        reward_amount=round(shares * (target - entry), 2),
        risk_reward=round((target - entry) / risk_per_share, 2),
        pct_of_account=round(cost / account_balance * 100.0, 1),
    )
