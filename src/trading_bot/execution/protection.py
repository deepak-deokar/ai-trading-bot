"""Immutable protective instructions and explicit conservative OHLC evidence."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from trading_bot.domain.contracts import ExactPositive
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel
from trading_bot.domain.positions import PositionDirection
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote


class ProtectiveTrigger(StrEnum):
    NO_EXIT = "NO_EXIT"
    STOP_TRIGGERED = "STOP_TRIGGERED"
    TARGET_TRIGGERED = "TARGET_TRIGGERED"
    STOP_TRIGGERED_AMBIGUOUS = "STOP_TRIGGERED_AMBIGUOUS"
    ALREADY_CLOSED = "ALREADY_CLOSED"


class ProtectiveInstruction(DomainModel):
    position_id: UUID
    direction: PositionDirection
    stop_price: ExactPositive
    target_price: ExactPositive | None = None
    created_at: datetime
    source_identity: str = Field(min_length=1)
    creation_quote: MarketQuote

    @field_validator("created_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def relationships(self) -> Self:
        quote = self.creation_quote
        if quote.canonical_symbol != "XAUUSD" or quote.timestamp != self.created_at:
            raise ValueError("creation requires an XAUUSD quote at exactly created_at")
        current = quote.price_for_side(self.direction.closing_side)
        if self.direction == PositionDirection.LONG:
            valid = self.stop_price < current and (
                self.target_price is None or self.target_price > current
            )
        else:
            valid = self.stop_price > current and (
                self.target_price is None or self.target_price < current
            )
        if not valid:
            raise ValueError(
                "protective levels must straddle current executable exit price"
            )
        return self

    @property
    def market_side(self) -> Literal["BID", "ASK"]:
        return "BID" if self.direction == PositionDirection.LONG else "ASK"

    def quote_trigger(self, quote: MarketQuote) -> ProtectiveTrigger:
        price = quote.price_for_side(self.direction.closing_side)
        if self.direction == PositionDirection.LONG:
            stop = price <= self.stop_price
            target = self.target_price is not None and price >= self.target_price
        else:
            stop = price >= self.stop_price
            target = self.target_price is not None and price <= self.target_price
        if stop:
            return ProtectiveTrigger.STOP_TRIGGERED
        if target:
            return ProtectiveTrigger.TARGET_TRIGGERED
        return ProtectiveTrigger.NO_EXIT


class ProtectiveBarEvidence(DomainModel):
    """Simulation evidence, never an observed quote or reconstructed tick path."""

    instruction: ProtectiveInstruction
    bar: QuoteBar
    evaluated_at: datetime
    source_market_data_id: str = Field(min_length=1)
    policy: Literal["STOP_FIRST_CONSERVATIVE"] = "STOP_FIRST_CONSERVATIVE"
    fill_convention: Literal["LEVEL_OR_WORSE_STOP_OPEN_TARGET_AT_LEVEL"] = (
        "LEVEL_OR_WORSE_STOP_OPEN_TARGET_AT_LEVEL"
    )

    @field_validator("evaluated_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def causal(self) -> Self:
        if self.evaluated_at < self.bar.closing_timestamp:
            raise ValueError("protective bar evaluation requires a completed bar")
        if self.instruction.created_at > self.bar.opening_timestamp:
            raise ValueError("instruction must be known at or before bar opening")
        return self

    @property
    def trigger(self) -> ProtectiveTrigger:
        p, b = self.instruction, self.bar
        if p.direction == PositionDirection.LONG:
            stop = b.bid_low <= p.stop_price
            target = p.target_price is not None and b.bid_high >= p.target_price
        else:
            stop = b.ask_high >= p.stop_price
            target = p.target_price is not None and b.ask_low <= p.target_price
        if stop and target:
            return ProtectiveTrigger.STOP_TRIGGERED_AMBIGUOUS
        if stop:
            return ProtectiveTrigger.STOP_TRIGGERED
        if target:
            return ProtectiveTrigger.TARGET_TRIGGERED
        return ProtectiveTrigger.NO_EXIT

    @property
    def fill_price(self) -> Decimal | None:
        if self.trigger == ProtectiveTrigger.NO_EXIT:
            return None
        if self.trigger == ProtectiveTrigger.TARGET_TRIGGERED:
            return self.instruction.target_price
        if self.instruction.direction == PositionDirection.LONG:
            return min(self.instruction.stop_price, self.bar.bid_open)
        return max(self.instruction.stop_price, self.bar.ask_open)
