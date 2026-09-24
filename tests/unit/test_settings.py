import pytest
from pydantic import ValidationError

from trading_bot.config.settings import Settings, load_settings

URL = "postgresql+psycopg://test:test@localhost:5432/test"


@pytest.mark.parametrize(
    "options",
    [
        {"trading_mode": "live"},
        {"live_trading_enabled": True},
        {"live_trading_confirmation": "I_CONFIRM"},
        {"trading_mode": "typo"},
        {"universe": []},
        {"universe": ["SPY", "SPY"]},
        {"universe": ["spy"]},
        {"bar_interval_seconds": 0},
        {"log_level": "anything"},
        {"database_url": "sqlite://"},
    ],
)
def test_rejects_unsafe_settings(options):
    with pytest.raises(ValidationError):
        Settings(**({"database_url": URL} | options))


def test_safe_defaults_and_secret_representation(settings):
    assert settings.trading_mode == "paper"
    assert not settings.live_trading_enabled
    assert URL not in repr(settings)


def test_missing_database_fails():
    with pytest.raises(ValidationError):
        Settings()


def test_environment_overrides_yaml(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text("trading_mode: backtest\nuniverse: [SPY]\n")
    monkeypatch.setenv("CONFIG_FILE", str(path))
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("TRADING_MODE", "shadow")
    config = load_settings()
    assert config.trading_mode == "shadow"
    assert config.universe == ("SPY",)


@pytest.mark.parametrize("content", ["database_url: secret", "[]", "unknown: value"])
def test_invalid_yaml_rejected(tmp_path, monkeypatch, content):
    path = tmp_path / "config.yaml"
    path.write_text(content)
    monkeypatch.setenv("CONFIG_FILE", str(path))
    monkeypatch.setenv("DATABASE_URL", URL)
    with pytest.raises(ValueError):
        load_settings()


def test_environment_live_cannot_be_masked_by_yaml(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text("trading_mode: paper")
    monkeypatch.setenv("CONFIG_FILE", str(path))
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("TRADING_MODE", "live")
    with pytest.raises(ValidationError):
        load_settings()


def test_invalid_database_error_hides_input():
    with pytest.raises(ValidationError) as error:
        Settings(database_url="invalid-url-with-secret")
    assert "invalid-url-with-secret" not in str(error.value)


def test_yaml_cannot_override_settings_sources(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text("_env_file: unexpected.env")
    monkeypatch.setenv("CONFIG_FILE", str(path))
    monkeypatch.setenv("DATABASE_URL", URL)
    with pytest.raises(ValueError, match="unknown configuration keys"):
        load_settings()


def test_groww_token_is_optional_and_secret(monkeypatch):
    monkeypatch.setenv("GROWW_ACCESS_TOKEN", "unit-test-secret")
    settings = Settings(database_url=URL)
    assert "unit-test-secret" not in repr(settings)
    assert settings.timeframe.value == "5minute"


def test_groww_token_cannot_be_loaded_from_yaml(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text("groww_access_token: forbidden")
    monkeypatch.setenv("CONFIG_FILE", str(path))
    with pytest.raises(ValueError, match="secrets"):
        load_settings()
