"""Tests that keep Streamlit isolated from reusable services."""

from __future__ import annotations

from pathlib import Path


def test_non_ui_modules_do_not_import_streamlit() -> None:
    src = Path("src/swing_spy")
    offenders = []
    for path in src.glob("*.py"):
        if path.name.startswith("__"):
            continue
        text = path.read_text()
        if "streamlit" in text:
            offenders.append(str(path))

    assert offenders == []
