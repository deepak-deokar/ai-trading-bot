"""Immutable transport schemas; predictions and requests have no execution methods."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trading_bot.domain.market import AdjustmentType, Exchange, Segment, Timeframe

Price = Annotated[
    Decimal, Field(gt=0, allow_inf_nan=False, max_digits=28, decimal_places=10)
]
Symbol = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9.&-]{0,31}$")]


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Timestamped(DomainModel):
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value.astimezone(UTC)


class Bar(Timestamped):
    """Timestamp is the candle OPEN in UTC; usable only after session-aware close."""

    timestamp_convention: Literal["open"] = "open"
    symbol: Symbol
    exchange: Exchange = Exchange.NSE
    segment: Segment = Segment.CASH
    timeframe: Timeframe = Timeframe.MIN_5
    interval_seconds: int = Field(default=300, gt=0)
    source: str = Field(default="local", pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    adjustment_type: AdjustmentType = AdjustmentType.RAW
    open_interest: int | None = Field(
        default=None, ge=0, le=9223372036854775807, strict=True
    )
    open: Price
    high: Price
    low: Price
    close: Price
    volume: int = Field(ge=0, le=9223372036854775807, strict=True)
    vwap: Price | None = None
    trade_count: int | None = Field(
        default=None, ge=0, le=9223372036854775807, strict=True
    )

    @model_validator(mode="after")
    def valid_ohlc(self) -> Self:
        seconds = int(self.timeframe.duration.total_seconds())
        if (
            "interval_seconds" in self.model_fields_set
            and self.interval_seconds != seconds
        ):
            raise ValueError("interval_seconds must match typed timeframe")
        object.__setattr__(self, "interval_seconds", seconds)
        if (
            not self.low
            <= min(self.open, self.close)
            <= max(self.open, self.close)
            <= self.high
        ):
            raise ValueError("inconsistent OHLC range")
        return self


class Prediction(Timestamped):
    prediction_id: UUID = Field(default_factory=uuid4)
    symbol: Symbol
    model_version: str = Field(min_length=1)
    probability_up: float = Field(ge=0, le=1)
    expected_return: float
    confidence: float = Field(ge=0, le=1)


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    CREATED = "created"
    RISK_APPROVED = "risk_approved"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


class OrderRequest(Timestamped):
    """Unapproved market-order proposal, never a broker command."""

    order_id: UUID = Field(default_factory=uuid4)
    symbol: Symbol
    side: Side
    quantity: int = Field(gt=0, strict=True)
    strategy_id: str = Field(min_length=1)
    prediction_id: UUID | None = None
    reason: str = Field(min_length=1)
