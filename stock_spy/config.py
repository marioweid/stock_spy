"""Configuration loading: secrets from the environment, watchlist from TOML."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from stock_spy.models import AppConfig

DEFAULT_CONFIG_PATH = Path("config.toml")


class Secrets(BaseSettings):
    """Secrets read from environment variables or a local ``.env`` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = Field(min_length=1)
    telegram_chat_id: str = Field(min_length=1)
    gemini_api_key: str = Field(min_length=1)


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
            f"Config file not found at {path}. Copy config.toml from the sample and edit it."
        )
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return AppConfig.model_validate(raw)
