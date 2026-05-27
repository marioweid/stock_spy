"""swing_spy — scan a market universe for swing-trade setups and alert on candidates.

A library first: import the scanner, the universe, or the pure setup/sizing math directly
(e.g. to evaluate one ticker or fetch a candidate's news from a REST layer), or run the
``swing-spy`` / ``python -m swing_spy`` entrypoint.
"""

from __future__ import annotations

from swing_spy.analysis import analyze, build_agent
from swing_spy.config import Secrets, load_config
from swing_spy.earnings import get_earnings
from swing_spy.history import download_history, quote_from_frame
from swing_spy.models import EarningsInfo, SwingConfig, SwingNote, SwingSetup, TradePlan
from swing_spy.report import Candidate, format_candidate_alert, render_markdown
from swing_spy.scanner import Scanner
from swing_spy.setups import find_swing_setup
from swing_spy.sizing import size_position
from swing_spy.universe import currency_for, get_universe

__all__ = [
    "Candidate",
    "EarningsInfo",
    "Scanner",
    "Secrets",
    "SwingConfig",
    "SwingNote",
    "SwingSetup",
    "TradePlan",
    "analyze",
    "build_agent",
    "currency_for",
    "download_history",
    "find_swing_setup",
    "format_candidate_alert",
    "get_earnings",
    "get_universe",
    "load_config",
    "quote_from_frame",
    "render_markdown",
    "size_position",
]
