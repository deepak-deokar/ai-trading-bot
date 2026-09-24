"""Validated configuration. Environment overrides YAML; secrets are env-only."""

import os
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from trading_bot.domain.market import Timeframe


class TradingMode(StrEnum):
    BACKTEST = "backtest"
    REPLAY = "replay"
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


class Settings(BaseSettings):
    """No settings combination enables execution during historical development."""

    model_config = SettingsConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True
    )
    trading_mode: TradingMode = TradingMode.PAPER
    live_trading_enabled: bool = False
    live_trading_confirmation: SecretStr = SecretStr("")
    groww_access_token: SecretStr | None = None
    database_url: SecretStr
    universe: tuple[str, ...] = ("RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK")
    bar_interval_seconds: int = Field(default=300, gt=0)
    log_level: str = "INFO"

    @property
    def timeframe(self) -> Timeframe:
        """Typed representation of the retained Phase 1 interval setting."""
        return next(
            t
            for t in Timeframe
            if int(t.duration.total_seconds()) == self.bar_interval_seconds
        )

    @field_validator("bar_interval_seconds")
    @classmethod
    def supported_interval(cls, value: int) -> int:
        if value not in {int(t.duration.total_seconds()) for t in Timeframe}:
            raise ValueError("unsupported bar interval")
        return value

    @field_validator("universe")
    @classmethod
    def validate_universe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        import re

        if not value or len(set(value)) != len(value):
            raise ValueError("universe must be nonempty and unique")
        if any(not re.fullmatch(r"[A-Z][A-Z0-9.&-]{0,31}", s) for s in value):
            raise ValueError("invalid or noncanonical symbol")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+psycopg" and bool(
                url.host and url.database and url.username and url.password
            )
        except Exception:
            valid = False
        if not valid:
            raise ValueError("a complete postgresql+psycopg URL is required")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_level(cls, value: str) -> str:
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("invalid log level")
        return value

    @model_validator(mode="after")
    def block_live(self) -> Self:
        if (
            self.trading_mode == TradingMode.LIVE
            or self.live_trading_enabled
            or self.live_trading_confirmation.get_secret_value()
        ):
            raise ValueError(
                "live trading is unavailable during historical-data development"
            )
        return self


def load_settings() -> Settings:
    """Load optional YAML beneath environment values. Do not load .env implicitly."""
    path = os.environ.get("CONFIG_FILE")
    defaults: dict[str, Any] = {}
    if path:
        data = yaml.safe_load(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError("configuration must be a YAML mapping")
        if any(not isinstance(key, str) for key in data):
            raise ValueError("configuration keys must be strings")
        if set(data) - Settings.model_fields.keys():
            raise ValueError("unknown configuration keys")
        forbidden = {"database_url", "live_trading_confirmation", "groww_access_token"}
        if forbidden.intersection(data):
            raise ValueError("secrets must be supplied through environment variables")
        defaults = data
    # BaseSettings init arguments outrank env; remove overridden YAML entries.
    environment_keys = {key.lower() for key in os.environ}
    return Settings(**{k: v for k, v in defaults.items() if k not in environment_keys})
