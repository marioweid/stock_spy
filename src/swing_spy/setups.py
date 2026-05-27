"""Deterministic swing-setup detection from technical indicators.

Pure and reproducible from the numbers, so any entry the scanner surfaces can be explained.
A setup requires a long-term uptrend (price above the 200-day average) and either a pullback
toward support/the 50-day average or an oversold reading, with a stop and target that line up.
"""

from __future__ import annotations

from spy_core.models import Technicals
from swing_spy.models import SetupKind, SwingSetup


def find_swing_setup(t: Technicals) -> SwingSetup:
    """Detect a swing-trade entry: an uptrend pullback or an oversold bounce near support."""
    price, support, resistance, atr = t.last_close, t.support, t.resistance, t.atr_14
    if price is None or support is None or resistance is None or atr is None:
        return SwingSetup(is_setup=False, rationale="Not enough price data for a setup.")
    if resistance <= support or t.sma_200 is None or price <= t.sma_200:
        return SwingSetup(is_setup=False, rationale="No uptrend — stand aside.")

    kind = _setup_kind(price, t.sma_50, t.rsi_14, support)
    if kind == "none":
        return SwingSetup(is_setup=False, rationale="In an uptrend but no clean entry yet.")

    stop = support - atr
    target_1 = resistance
    if price <= stop or target_1 <= price:
        return SwingSetup(is_setup=False, rationale="Risk/reward does not line up here.")
    target_2 = resistance + (resistance - support) * 0.5
    rationale = (
        "Pulled back toward support inside an uptrend."
        if kind == "pullback"
        else "Oversold while still in a long-term uptrend — bounce candidate."
    )
    return SwingSetup(
        is_setup=True,
        kind=kind,
        entry_low=round(min(price, support), 2),
        entry_high=round(price, 2),
        stop=round(stop, 2),
        target_1=round(target_1, 2),
        target_2=round(target_2, 2),
        risk_reward=round((target_1 - price) / (price - stop), 2),
        rationale=rationale,
    )


def _setup_kind(price: float, sma50: float | None, rsi: float | None, support: float) -> SetupKind:
    """Classify the entry: oversold bounce, pullback to support/SMA50, or none."""
    if rsi is not None and rsi < 35:
        return "oversold_bounce"
    near_support = price <= support * 1.05
    pulled_back = sma50 is not None and price <= sma50 * 1.03 and (rsi is None or rsi < 55)
    if near_support or pulled_back:
        return "pullback"
    return "none"
