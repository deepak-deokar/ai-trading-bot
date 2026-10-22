import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_bot.journal.demo import synthetic_events
from trading_bot.journal.models import (
    AccountSnapshot,
    DecisionEvent,
    EventType,
    MarketSnapshot,
    ReasonCode,
)


def sample(**changes):
    return DecisionEvent.model_validate(
        dict(
            timestamp="2026-01-05T17:30:00+05:30",
            event_type="MARKET_EVALUATED",
            canonical_symbol="XAUUSD",
            reason_code="SYNTHETIC_DEMONSTRATION",
            summary="Synthetic test",
            source="test",
            **changes,
        )
    )


def test_stable_taxonomy():
    assert (
        [e.value for e in EventType]
        == """MARKET_EVALUATED SETUP_DETECTED
    SETUP_REJECTED TRADE_INTENT_CREATED TRADE_REJECTED TRADE_APPROVED ORDER_REQUESTED
    ORDER_SUBMITTED ORDER_REJECTED ORDER_FILLED POSITION_OPENED STOP_CREATED STOP_MOVED
    TARGET_CREATED TARGET_MOVED BREAKEVEN_ACTIVATED TRAILING_STOP_ACTIVATED
    TRAILING_STOP_MOVED PARTIAL_PROFIT_TAKEN POSITION_EXIT_REQUESTED POSITION_CLOSED
    KILL_SWITCH_TRIGGERED MANUAL_OVERRIDE SYSTEM_SAFETY_BLOCK""".split()
    )
    assert (
        [e.value for e in ReasonCode]
        == """SIGNAL_QUALIFIED SIGNAL_TOO_WEAK
    SPREAD_TOO_WIDE RISK_TOO_HIGH MINIMUM_LOT_EXCEEDS_RISK DAILY_LOSS_LIMIT
    MAX_DRAWDOWN_LIMIT POSITION_ALREADY_OPEN NEWS_RISK SESSION_RESTRICTION
    STOP_INITIALIZED STOP_MOVED_TO_BREAKEVEN STOP_TRAILED TARGET_RECALCULATED
    TREND_REVERSAL STOP_HIT TARGET_HIT MANUAL_EXIT SYNTHETIC_DEMONSTRATION""".split()
    )


def test_utc_and_exact_serialization_and_immutability():
    data = {"nested": [{"price": Decimal("4102.500000000000000001")}]}
    event = sample(details=data, previous_value=Decimal("4097.80"))
    data["nested"].clear()
    assert event.timestamp == datetime(2026, 1, 5, 12, tzinfo=UTC)
    encoded = json.loads(event.model_dump_json())
    assert encoded["details"]["nested"][0]["price"] == "4102.500000000000000001"
    assert encoded["previous_value"] == "4097.80"
    assert DecisionEvent.model_validate(encoded) == event
    with pytest.raises(TypeError):
        event.details["nested"][0]["price"] = "1"
    with pytest.raises(ValidationError):
        event.summary = "changed"
    with pytest.raises(TypeError):
        sample().details["new"] = True
    with pytest.raises(TypeError):
        MarketSnapshot().feature_values["new"] = True


@pytest.mark.parametrize(
    "field,value",
    [
        ("timestamp", "2026-01-05T12:00:00"),
        ("event_type", "UNKNOWN"),
        ("reason_code", "UNKNOWN"),
        ("schema_version", 2),
        ("summary", ""),
        ("details", {"risk": 2.50}),
        ("details", {"bad": Decimal("NaN")}),
        ("previous_value", float("inf")),
        ("trade_id", "invalid"),
    ],
)
def test_invalid_events(field, value):
    data = sample().model_dump(mode="json") | {field: value}
    with pytest.raises(ValidationError):
        DecisionEvent.model_validate(data)


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "API-Key",
        "mt5Password",
        "access_token",
        "secret",
        "private_key",
        "Authorization",
    ],
)
@pytest.mark.parametrize("field", ["details", "previous_value", "new_value"])
def test_nested_secret_fields_rejected(field, key):
    with pytest.raises(ValidationError, match="sensitive") as error:
        sample(**{field: {"nested": [{key: "sentinel-do-not-expose"}]}})
    assert "sentinel-do-not-expose" not in str(error.value)


def test_snapshots_exact_and_generic():
    market = MarketSnapshot(
        timestamp="2026-01-05T17:30:00+05:30",
        bid="4102.50",
        ask="4102.60",
        feature_values={"atr": Decimal("1.20")},
    )
    account = AccountSnapshot(
        account_currency="USD",
        balance=Decimal("500"),
        daily_realized_pnl="-2.50",
        current_drawdown="2.50",
    )
    assert market.timestamp.hour == 12
    assert market.model_dump(mode="json")["feature_values"] == {"atr": "1.20"}
    assert account.model_dump(mode="json")["balance"] == "500"
    assert AccountSnapshot(account_currency="INR", balance="500").balance == Decimal(
        500
    )


@pytest.mark.parametrize(
    "values",
    [
        {"bid": "-1"},
        {"spread": "-1"},
        {"ask": 2.5},
        {"timestamp": "2026-01-01"},
        {"feature_values": {"apiKey": "blocked"}},
    ],
)
def test_invalid_market(values):
    with pytest.raises(ValidationError):
        MarketSnapshot(**values)


@pytest.mark.parametrize(
    "values",
    [
        {"balance": "NaN"},
        {"used_margin": "-1"},
        {"open_position_count": True},
        {"balance": 500.0},
        {"timestamp": "2026-01-01"},
        {"current_drawdown": "-1"},
    ],
)
def test_invalid_account(values):
    with pytest.raises(ValidationError):
        AccountSnapshot(account_currency="USD", **values)


def test_synthetic_demo_deterministic():
    events = synthetic_events(Path("config/xauusd_v1.yaml"))
    assert events == synthetic_events(Path("config/xauusd_v1.yaml"))
    assert len(events) == 7
    assert events[2].details["allowed_risk_usd"] == "2.50"
    assert events[2].account_snapshot.balance == Decimal("500")
    assert events[2].trade_id != events[3].trade_id
    assert all(
        e.details["synthetic"] and not e.details["rules_implemented"] for e in events
    )
