"""Immutable, UTC decision vocabulary and exact, credential-safe audit payloads."""

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field, field_serializer, field_validator

from trading_bot.domain.instruments import Currency
from trading_bot.domain.market import Timeframe, utc
from trading_bot.domain.models import DomainModel, Symbol


class EventType(StrEnum):
    MARKET_EVALUATED = "MARKET_EVALUATED"
    SETUP_DETECTED = "SETUP_DETECTED"
    SETUP_REJECTED = "SETUP_REJECTED"
    TRADE_INTENT_CREATED = "TRADE_INTENT_CREATED"
    TRADE_REJECTED = "TRADE_REJECTED"
    TRADE_APPROVED = "TRADE_APPROVED"
    ORDER_REQUESTED = "ORDER_REQUESTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"
    POSITION_OPENED = "POSITION_OPENED"
    STOP_CREATED = "STOP_CREATED"
    STOP_MOVED = "STOP_MOVED"
    TARGET_CREATED = "TARGET_CREATED"
    TARGET_MOVED = "TARGET_MOVED"
    BREAKEVEN_ACTIVATED = "BREAKEVEN_ACTIVATED"
    TRAILING_STOP_ACTIVATED = "TRAILING_STOP_ACTIVATED"
    TRAILING_STOP_MOVED = "TRAILING_STOP_MOVED"
    PARTIAL_PROFIT_TAKEN = "PARTIAL_PROFIT_TAKEN"
    POSITION_EXIT_REQUESTED = "POSITION_EXIT_REQUESTED"
    POSITION_CLOSED = "POSITION_CLOSED"
    KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    SYSTEM_SAFETY_BLOCK = "SYSTEM_SAFETY_BLOCK"


class ReasonCode(StrEnum):
    SIGNAL_QUALIFIED = "SIGNAL_QUALIFIED"
    SIGNAL_TOO_WEAK = "SIGNAL_TOO_WEAK"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    RISK_TOO_HIGH = "RISK_TOO_HIGH"
    MINIMUM_LOT_EXCEEDS_RISK = "MINIMUM_LOT_EXCEEDS_RISK"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN_LIMIT = "MAX_DRAWDOWN_LIMIT"
    POSITION_ALREADY_OPEN = "POSITION_ALREADY_OPEN"
    NEWS_RISK = "NEWS_RISK"
    SESSION_RESTRICTION = "SESSION_RESTRICTION"
    STOP_INITIALIZED = "STOP_INITIALIZED"
    STOP_MOVED_TO_BREAKEVEN = "STOP_MOVED_TO_BREAKEVEN"
    STOP_TRAILED = "STOP_TRAILED"
    TARGET_RECALCULATED = "TARGET_RECALCULATED"
    TREND_REVERSAL = "TREND_REVERSAL"
    STOP_HIT = "STOP_HIT"
    TARGET_HIT = "TARGET_HIT"
    MANUAL_EXIT = "MANUAL_EXIT"
    SYNTHETIC_DEMONSTRATION = "SYNTHETIC_DEMONSTRATION"


def freeze(value: Any) -> Any:
    """Copy/freeze JSON-like data; no arbitrary objects, floats or secret fields.

    Decimal is encoded as an exact string, including its decimal scale. This
    guard cannot identify secrets deliberately embedded in unlabelled prose.
    """
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("audit metadata keys must be strings")
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if any(
                word in normalized
                for word in (
                    "password",
                    "passwd",
                    "secret",
                    "token",
                    "apikey",
                    "privatekey",
                    "credential",
                    "authorization",
                    "databaseurl",
                )
            ):
                raise ValueError("sensitive metadata field prohibited")
            result[key] = freeze(item)
        return MappingProxyType(result)
    if isinstance(value, list | tuple):
        return tuple(freeze(item) for item in value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("audit Decimal must be finite")
        return str(value)
    if value is None or type(value) in (str, int, bool):
        return value
    raise ValueError("audit values require JSON scalars or Decimal; floats prohibited")


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value


Money = Annotated[Decimal, Field(allow_inf_nan=False)]
PositivePrice = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
NonnegativeMoney = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class AuditModel(DomainModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        hide_input_in_errors=True,
        validate_default=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def no_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("use Decimal or an exact string, not float")
        return value


class MarketSnapshot(AuditModel):
    timestamp: datetime | None = None
    bid: PositivePrice | None = None
    ask: PositivePrice | None = None
    spread: NonnegativeMoney | None = None
    mid: PositivePrice | None = None
    timeframe: Timeframe | None = None
    feature_values: Mapping[str, Any] = Field(default_factory=dict)
    market_regime: str | None = None
    volatility_state: str | None = None
    session_label: str | None = None

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @field_validator("feature_values", mode="after")
    @classmethod
    def safe_features(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return cast(Mapping[str, Any], freeze(value))

    @field_serializer("feature_values")
    def serialize_features(self, value: Mapping[str, Any]) -> Any:
        return thaw(value)


class AccountSnapshot(AuditModel):
    account_currency: Currency
    timestamp: datetime | None = None
    balance: Money | None = None
    equity: Money | None = None
    free_margin: Money | None = None
    used_margin: NonnegativeMoney | None = None
    open_position_count: int | None = Field(default=None, ge=0, strict=True)
    daily_realized_pnl: Money | None = None
    daily_unrealized_pnl: Money | None = None
    current_drawdown: NonnegativeMoney | None = None

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None


class DecisionEvent(AuditModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    event_type: EventType
    canonical_symbol: Symbol
    strategy_id: str | None = Field(default=None, min_length=1, max_length=128)
    evaluation_id: UUID | None = None
    trade_id: UUID | None = None
    position_id: UUID | None = None
    order_id: UUID | None = None
    strategy_run_id: UUID | None = None
    reason_code: ReasonCode
    summary: str = Field(min_length=1, max_length=1000)
    details: Mapping[str, Any] = Field(default_factory=dict)
    market_snapshot: MarketSnapshot | None = None
    account_snapshot: AccountSnapshot | None = None
    previous_value: Any = None
    new_value: Any = None
    source: str = Field(min_length=1, max_length=128)
    schema_version: Literal[1] = 1

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("details", "previous_value", "new_value", mode="after")
    @classmethod
    def safe_payload(cls, value: Any) -> Any:
        return freeze(value)

    @field_serializer("details", "previous_value", "new_value")
    def serialize_payload(self, value: Any) -> Any:
        return thaw(value)
