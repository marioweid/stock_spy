"""Tests for Streamlit-only dashboard wiring."""

from __future__ import annotations

from pathlib import Path


def test_streamlit_app_modules_import() -> None:
    from swing_spy.streamlit_app import app, components, service_factory

    assert app is not None
    assert components is not None
    assert service_factory is not None


def test_lifecycle_service_factory_does_not_cache_sqlite_connection() -> None:
    source = Path("src/swing_spy/streamlit_app/service_factory.py").read_text()
    factory_prefix = source.split("def get_lifecycle_service", maxsplit=1)[0]

    assert "@st.cache_resource" not in factory_prefix
