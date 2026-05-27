"""Configuration loading for the scanner: settings from TOML, secrets from the environment."""

from __future__ import annotations

import tomllib
from pathlib import Path

from spy_core.config import Secrets
from swing_spy.models import SwingConfig

DEFAULT_CONFIG_PATH = Path("swing_config.toml")

__all__ = ["DEFAULT_CONFIG_PATH", "Secrets", "load_config"]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> SwingConfig:
    """Load the scanner settings and universe selection from a TOML file.

    Args:
        path: Path to the TOML config file.

    Returns:
        The parsed scanner configuration.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found at {path}. "
            "Copy swing_config_example.toml to swing_config.toml and edit it."
        )
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return SwingConfig.model_validate(raw)
