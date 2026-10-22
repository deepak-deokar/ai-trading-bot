"""G1A identity and configuration boundaries; no market or execution access."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_bot.config.research import (
    FutureRiskSettings,
    ReferenceAccount,
    XAUUSDResearchConfig,
    load_xauusd_research,
)
from trading_bot.domain.instruments import AssetClass, Currency, Instrument
from trading_bot.domain.market import Exchange, Segment
from trading_bot.domain.models import Bar

PROFILE = Path(__file__).resolve().parents[2] / "config/xauusd_v1.yaml"


def test_xauusd_profile_identity_and_account():
    profile = load_xauusd_research(PROFILE)
    instrument = profile.instrument
    assert instrument.symbol == "XAUUSD"
    assert instrument.asset_class == AssetClass.SPOT_METAL
    assert instrument.base_asset == "XAU"
    assert instrument.quote_currency == Currency.USD
    assert instrument.exchange is None and instrument.segment is None
    assert "provider_symbol" not in instrument.model_dump()
    assert profile.account.account_currency == Currency.USD
    assert profile.account.reference_starting_balance == Decimal("500")
    assert isinstance(profile.account.reference_starting_balance, Decimal)
    assert all(value is None for value in profile.future_risk.model_dump().values())
    assert profile.research_status == "DOMAIN_CONFIGURATION_ONLY"
    assert profile.target_platform == "MT5"
    assert profile.supports_long and profile.supports_short
    assert profile.requires_bid_ask and profile.uses_lot_quantity
    assert profile.requires_contract_specification


def test_existing_nse_and_inr_remain_independent():
    equity = Instrument(
        symbol="RELIANCE",
        asset_class=AssetClass.EQUITY,
        base_asset="RELIANCE",
        quote_currency=Currency.INR,
        exchange=Exchange.NSE,
        segment=Segment.CASH,
    )
    account = ReferenceAccount(
        account_currency=Currency.INR, reference_starting_balance=Decimal("100000")
    )
    bar = Bar(
        symbol=equity.symbol,
        timestamp=datetime(2026, 1, 5, tzinfo=UTC),
        open=100,
        high=101,
        low=99,
        close=100,
        volume=10,
    )
    assert bar.exchange == Exchange.NSE and bar.segment == Segment.CASH
    assert account.account_currency == Currency.INR
    assert load_xauusd_research(PROFILE).account.account_currency == Currency.USD


@pytest.mark.parametrize(
    "changes",
    [
        {"asset_class": "EQUITY"},
        {"base_asset": "USD"},
        {"quote_currency": "INR"},
        {"exchange": "NSE", "segment": "CASH"},
        {"exchange": "NSE"},
        {"provider_symbol": "XAUUSDm"},
    ],
)
def test_invalid_gold_identity(changes):
    data = load_xauusd_research(PROFILE).instrument.model_dump()
    with pytest.raises(ValidationError):
        Instrument.model_validate(data | changes)


@pytest.mark.parametrize(
    "currency,balance",
    [
        ("EUR", "500"),
        ("USD", "0"),
        ("USD", "-1"),
        ("USD", "NaN"),
        ("USD", "Infinity"),
    ],
)
def test_invalid_reference_account(currency, balance):
    with pytest.raises(ValidationError):
        ReferenceAccount(account_currency=currency, reference_starting_balance=balance)


@pytest.mark.parametrize(
    "account",
    [
        {"account_currency": "INR", "reference_starting_balance": "500"},
        {"account_currency": "USD", "reference_starting_balance": "1000"},
    ],
)
def test_v1_account_pair_is_explicit(account):
    data = load_xauusd_research(PROFILE).model_dump() | {"account": account}
    with pytest.raises(ValidationError):
        XAUUSDResearchConfig.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("risk_per_trade_percent", 0),
        ("maximum_daily_loss_percent", 101),
        ("maximum_drawdown_percent", "NaN"),
        ("maximum_open_positions", True),
        ("maximum_open_positions", -1),
    ],
)
def test_future_risk_validation(field, value):
    with pytest.raises(ValidationError):
        FutureRiskSettings.model_validate({field: value})


@pytest.mark.parametrize(
    "field",
    [
        "api_key",
        "password",
        "broker_server",
        "fixed_lot",
        "live_trading_enabled",
    ],
)
def test_profile_rejects_credentials_and_execution_fields(field):
    data = load_xauusd_research(PROFILE).model_dump() | {field: "not-permitted"}
    with pytest.raises(ValidationError):
        XAUUSDResearchConfig.model_validate(data)


def test_yaml_requires_mapping(tmp_path):
    path = tmp_path / "invalid.yaml"
    path.write_text("- XAUUSD\n")
    with pytest.raises(ValueError, match="mapping"):
        load_xauusd_research(path)
