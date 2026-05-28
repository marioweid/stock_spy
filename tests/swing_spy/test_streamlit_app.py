"""Smoke tests for Streamlit UI package boundaries."""

from __future__ import annotations


def test_streamlit_app_modules_import() -> None:
    from swing_spy.streamlit_app import app, components, service_factory

    assert app is not None
    assert components is not None
    assert service_factory is not None
