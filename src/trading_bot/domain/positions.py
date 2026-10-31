"""Direction-aware position snapshots, without execution or monetary accounting."""

from datetime import datetime
from decimal import Decimal, localcontext
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from trading_bot.domain.contracts import ExactPositive
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side, Symbol


class PositionDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def opening_side(self) -> Side:
        return Side.BUY if self == PositionDirection.LONG else Side.SELL

    @property
    def closing_side(self) -> Side:
        return Side.SELL if self == PositionDirection.LONG else Side.BUY


def raw_price_movement(
    direction: PositionDirection, entry_price: Decimal, exit_price: Decimal
) -> Decimal:
    """Positive is favorable, negative unfavorable. No volume or money conversion."""
    direction = PositionDirection(direction)
    for price in (entry_price, exit_price):
        if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
            raise ValueError("prices must be positive finite Decimal values")
    # Enough precision for exact subtraction, independent of ambient precision.
    # Finite Decimal exponents are integers (the type also permits special values).
    exponent = min(
        int(entry_price.as_tuple().exponent), int(exit_price.as_tuple().exponent)
    )
    with localcontext() as context:
        context.prec = max(entry_price.adjusted(), exit_price.adjusted()) - exponent + 2
        if direction == PositionDirection.LONG:
            return exit_price - entry_price
        return entry_price - exit_price


class PositionSnapshot(DomainModel):
    """One open or fully closed position; no netting/hedging or partial-close policy."""

    position_id: UUID = Field(default_factory=uuid4)
    canonical_symbol: Symbol
    direction: PositionDirection
    volume: ExactPositive
    entry_price: ExactPositive
    opened_at: datetime
    closed_at: datetime | None = None
    exit_price: ExactPositive | None = None

    @field_validator("opened_at", "closed_at")
    @classmethod
    def utc_time(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def valid_close(self) -> Self:
        if (self.closed_at is None) != (self.exit_price is None):
            raise ValueError("closed_at and exit_price must be supplied together")
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError("closed_at cannot precede opened_at")
        return self
