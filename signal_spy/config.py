"""Configuration loading: secrets from the environment, watchlist from TOML."""

from __future__ import annotations

import tomllib
from pathlib import Path

from signal_spy.models import AppConfig
from spy_core.config import Secrets

DEFAULT_CONFIG_PATH = Path("signal_config.toml")

__all__ = ["DEFAULT_CONFIG_PATH", "Secrets", "load_config"]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Load the watchlist and runtime settings from a TOML file.

    Args:
        path: Path to the TOML config file.

    Returns:
        The parsed application configuration.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found at {path}. "
            "Copy signal_config_example.toml to signal_config.toml and edit it."
        )
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return AppConfig.model_validate(raw)
