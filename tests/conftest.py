import os

import pytest


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in list(os.environ):
        if key.upper() in {
            "DATABASE_URL",
            "GROWW_ACCESS_TOKEN",
            "CONFIG_FILE",
            "TRADING_MODE",
            "LIVE_TRADING_ENABLED",
            "LIVE_TRADING_CONFIRMATION",
            "UNIVERSE",
            "BAR_INTERVAL_SECONDS",
            "LOG_LEVEL",
        }:
            monkeypatch.delenv(key)


@pytest.fixture
def settings():
    from trading_bot.config.settings import Settings

    return Settings(database_url="postgresql+psycopg://test:test@localhost:5432/test")
