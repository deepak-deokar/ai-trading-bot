"""Quoted market sides only; no fills, slippage or monetary accounting."""

from datetime import datetime
from decimal import Decimal, localcontext
from enum import StrEnum
from typing import Self

from pydantic import field_validator, model_validator

from trading_bot.domain.contracts import ContractSpecification, ExactPositive
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side, Symbol
from trading_bot.domain.positions import PositionDirection, raw_price_movement


class QuoteSource(StrEnum):
    TEST_FIXTURE = "TEST_FIXTURE"
    HISTORICAL_PROVIDER = "HISTORICAL_PROVIDER"
    MT5_TERMINAL = "MT5_TERMINAL"


class SpreadAlignmentError(ValueError):
    """Quoted spread is not an integer multiple of the supplied tick size."""


class MarketQuote(DomainModel):
    canonical_symbol: Symbol
    timestamp: datetime
    bid: ExactPositive
    ask: ExactPositive
    source: QuoteSource | None = None

    @field_validator("timestamp")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def not_crossed(self) -> Self:
        if self.ask < self.bid:
            raise ValueError("crossed quote: ask must be >= bid")
        return self

    @property
    def spread(self) -> Decimal:
        return raw_price_movement(PositionDirection.LONG, self.bid, self.ask)

    @property
    def mid(self) -> Decimal:
        """Analytical midpoint; never selected as the executable quote side."""
        exponent = min(
            int(self.bid.as_tuple().exponent), int(self.ask.as_tuple().exponent)
        )
        with localcontext() as context:
            context.prec = max(self.bid.adjusted(), self.ask.adjusted()) - exponent + 3
            return (self.bid + self.ask) / Decimal(2)

    def price_for_side(self, side: Side) -> Decimal:
        """Conceptual immediate execution quote, regardless of open/close intent."""
        side = Side(side)
        return self.ask if side == Side.BUY else self.bid

    def spread_in_ticks(self, specification: ContractSpecification) -> Decimal:
        """Exact whole tick count; reject symbol mismatch or fractional ticks."""
        if self.canonical_symbol != specification.canonical_symbol:
            raise ValueError("quote and contract canonical symbols must match")
        numerator, denominator = self.spread.as_integer_ratio()
        tick_numerator, tick_denominator = specification.tick_size.as_integer_ratio()
        ticks, remainder = divmod(
            numerator * tick_denominator, denominator * tick_numerator
        )
        if remainder:
            raise SpreadAlignmentError("spread is not exactly tick-aligned")
        return Decimal(ticks)
