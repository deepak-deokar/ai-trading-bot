"""Dedicated immutable five-minute research bars; not NSE candles."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel

BarPrice = Annotated[
    Decimal,
    Field(strict=True, gt=0, allow_inf_nan=False, max_digits=28, decimal_places=10),
]


class QuoteBar(DomainModel):
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    interval: Literal["5minute"] = "5minute"
    opening_timestamp: datetime
    bid_open: BarPrice
    bid_high: BarPrice
    bid_low: BarPrice
    bid_close: BarPrice
    ask_open: BarPrice
    ask_high: BarPrice
    ask_low: BarPrice
    ask_close: BarPrice
    tick_count: int = Field(gt=0, strict=True, le=9223372036854775807)

    @field_validator("opening_timestamp")
    @classmethod
    def opening(cls, value: datetime) -> datetime:
        value = utc(value)
        if value.minute % 5 or value.second or value.microsecond:
            raise ValueError("opening_timestamp must align to a UTC five-minute bin")
        return value

    @model_validator(mode="after")
    def ohlc(self) -> Self:
        for side in ("bid", "ask"):
            opening, high, low, close = (
                getattr(self, f"{side}_{key}")
                for key in ("open", "high", "low", "close")
            )
            if not low <= min(opening, close) <= max(opening, close) <= high:
                raise ValueError("invalid side OHLC range")
        for key in ("open", "high", "low", "close"):
            if getattr(self, f"ask_{key}") < getattr(self, f"bid_{key}"):
                raise ValueError("crossed side OHLC")
        return self

    @property
    def closing_timestamp(self) -> datetime:
        return self.opening_timestamp + timedelta(minutes=5)
