"""Strict simulated orders and scripted intents, separate from live vocabulary."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Price, Symbol


class BacktestError(ValueError):
    """Sanitized simulation input or accounting failure."""


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"


class Status(StrEnum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    TRIGGERED = "TRIGGERED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TradeIntent(DomainModel):
    reference: str = Field(min_length=1, max_length=100)
    symbol: Symbol
    side: Side
    quantity: int = Field(gt=0, le=1_000_000_000, strict=True)
    order_type: OrderType = OrderType.MARKET
    created_at: datetime
    feature_timestamp: datetime
    limit_price: Price | None = None
    trigger_price: Price | None = None
    oco_group: str | None = Field(default=None, min_length=1, max_length=100)
    required_features: tuple[str, ...] = ()
    time_in_force: Literal["DAY"] = "DAY"
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if not self.metadata:
            data.pop("metadata", None)
        return data

    @field_validator("created_at", "feature_timestamp")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def prices(self) -> Self:
        if (self.order_type == OrderType.LIMIT) != (self.limit_price is not None):
            raise ValueError("LIMIT requires limit price; other types forbid it")
        if (self.order_type == OrderType.STOP_MARKET) != (
            self.trigger_price is not None
        ):
            raise ValueError(
                "STOP_MARKET requires trigger price; other types forbid it"
            )
        if self.feature_timestamp >= self.created_at:
            raise ValueError("decision must follow its feature's candle opening")
        if self.oco_group and self.side != Side.SELL:
            raise ValueError("V1 OCO groups are long-position exit orders only")
        return self


class Transition(DomainModel):
    timestamp: datetime
    status: Status
    reason: str


class SimOrder(DomainModel):
    order_id: str
    intent: TradeIntent
    eligible_from: datetime | None
    status: Status = Status.CREATED
    filled_quantity: int = 0
    executed_turnover: Decimal = Decimal(0)
    transitions: tuple[Transition, ...] = ()
    forced: bool = False

    @property
    def remaining(self) -> int:
        return self.intent.quantity - self.filled_quantity

    @property
    def active(self) -> bool:
        return self.status in {
            Status.ACCEPTED,
            Status.PENDING,
            Status.TRIGGERED,
            Status.PARTIALLY_FILLED,
        }

    def transition(
        self, status: Status, timestamp: datetime, reason: str
    ) -> "SimOrder":
        if not self.active and self.status != Status.CREATED:
            raise BacktestError("terminal order cannot transition")
        return self.model_copy(
            update={
                "status": status,
                "transitions": self.transitions
                + (Transition(timestamp=timestamp, status=status, reason=reason),),
            }
        )
