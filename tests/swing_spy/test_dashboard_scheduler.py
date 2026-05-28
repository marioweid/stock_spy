"""Tests for dashboard candidate persistence wiring."""

from __future__ import annotations

from pathlib import Path

from swing_spy.config import Secrets
from swing_spy.models import SwingConfig
from swing_spy.scheduler import build_scanner


async def test_build_scanner_wires_dashboard_candidate_recorder(tmp_path: Path) -> None:
    config = SwingConfig(db_path=str(tmp_path / "swing.sqlite3"))
    secrets = Secrets(
        telegram_bot_token="T",
        telegram_chat_id="C",
        gemini_api_key="G",
    )

    async with build_scanner(config, secrets) as scanner:
        assert scanner.record_dashboard_candidate is not None
