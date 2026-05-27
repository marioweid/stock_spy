"""Shared secrets, read from the environment or a local ``.env`` file."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Secrets(BaseSettings):
    """Secrets read from environment variables or a local ``.env`` file.

    Shared by every spy tool — Telegram delivery and the Gemini API both live here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = Field(min_length=1)
    telegram_chat_id: str = Field(min_length=1)
    gemini_api_key: str = Field(min_length=1)
