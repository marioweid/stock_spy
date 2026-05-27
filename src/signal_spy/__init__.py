"""signal_spy — buy/hold/sell signals and portfolio-protection alerts.

A library first: import the engine pieces directly (e.g. to score a ticker or build a report
outside the CLI), or run the ``signal-spy`` / ``python -m signal_spy`` entrypoint.
"""

from __future__ import annotations

from signal_spy.analysis import ReportBundle, analyze, assemble_report, build_agent
from signal_spy.config import Secrets, load_config
from signal_spy.models import (
    AppConfig,
    EquityReport,
    Fundamentals,
    Holding,
    Portfolio,
    RiskAssessment,
    Scores,
    Signal,
    Subscription,
)
from signal_spy.monitor import Monitor
from signal_spy.scoring import assess_risk, composite, score_fundamentals, score_technicals, verdict

__all__ = [
    "AppConfig",
    "EquityReport",
    "Fundamentals",
    "Holding",
    "Monitor",
    "Portfolio",
    "ReportBundle",
    "RiskAssessment",
    "Scores",
    "Secrets",
    "Signal",
    "Subscription",
    "analyze",
    "assemble_report",
    "assess_risk",
    "build_agent",
    "composite",
    "load_config",
    "score_fundamentals",
    "score_technicals",
    "verdict",
]
