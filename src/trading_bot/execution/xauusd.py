"""One immutable synthetic/research lifecycle, without account P&L or orders."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID, uuid5

from pydantic import Field, model_validator

from trading_bot.domain.contracts import ExactPositive
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side
from trading_bot.domain.positions import (
    PositionDirection,
    PositionSnapshot,
    raw_price_movement,
)
from trading_bot.domain.quotes import MarketQuote


class ExecutionError(ValueError):
    """Invalid lifecycle transition or unavailable executable observation."""


class ExecutionFill(DomainModel):
    execution_id: UUID
    position_id: UUID
    intent: Literal["OPEN", "CLOSE"]
    direction: PositionDirection
    action: Side
    executed_price: ExactPositive
    quote: MarketQuote
    source_market_data_id: str = Field(min_length=1)
    strategy_decision_id: UUID | None = None

    @model_validator(mode="after")
    def executable_side(self) -> Self:
        expected = (
            self.direction.opening_side
            if self.intent == "OPEN"
            else self.direction.closing_side
        )
        if self.quote.canonical_symbol != "XAUUSD":
            raise ValueError("execution requires canonical XAUUSD")
        if self.action != expected or self.executed_price != self.quote.price_for_side(
            expected
        ):
            raise ValueError("fill must use the direction/intent executable quote side")
        return self

    @property
    def timestamp(self) -> datetime:
        return self.quote.timestamp

    @property
    def canonical_symbol(self) -> str:
        return self.quote.canonical_symbol

    @property
    def bid(self) -> Decimal:
        return self.quote.bid

    @property
    def ask(self) -> Decimal:
        return self.quote.ask

    @property
    def spread(self) -> Decimal:
        return self.quote.spread


class XAUUSDExecution(DomainModel):
    """Single FLAT -> OPEN -> CLOSED lifecycle; reuse a new ID for another run."""

    simulation_id: UUID
    position: PositionSnapshot | None = None
    fills: tuple[ExecutionFill, ...] = ()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.position is None:
            if self.fills:
                raise ValueError("flat lifecycle cannot have fills")
            return self
        p = self.position
        if p.canonical_symbol != "XAUUSD" or p.position_id != uuid5(
            self.simulation_id, "position"
        ):
            raise ValueError("position identity mismatch")
        closed = p.closed_at is not None
        if len(self.fills) != (2 if closed else 1):
            raise ValueError("position and fill lifecycle disagree")
        for i, fill in enumerate(self.fills):
            intent = "CLOSE" if i else "OPEN"
            if (
                fill.intent != intent
                or fill.direction != p.direction
                or fill.position_id != p.position_id
                or fill.execution_id != uuid5(self.simulation_id, intent)
                or fill.timestamp != (p.closed_at if i else p.opened_at)
                or fill.executed_price != (p.exit_price if i else p.entry_price)
            ):
                raise ValueError("fill does not match position lifecycle")
        return self

    @property
    def status(self) -> str:
        return (
            "FLAT"
            if self.position is None
            else "CLOSED" if self.position.closed_at is not None else "OPEN"
        )

    @property
    def price_movement(self) -> Decimal | None:
        if self.position is None or self.position.exit_price is None:
            return None
        return raw_price_movement(
            self.position.direction, self.position.entry_price, self.position.exit_price
        )

    def _quote(self, quote: MarketQuote, timestamp: datetime) -> MarketQuote:
        validated = MarketQuote.model_validate(quote.model_dump())
        if validated.canonical_symbol != "XAUUSD" or validated.timestamp != utc(
            timestamp
        ):
            raise ExecutionError(
                "execution requires an XAUUSD quote observed at exactly T"
            )
        return validated

    def open(
        self,
        direction: PositionDirection,
        volume: Decimal,
        quote: MarketQuote,
        *,
        timestamp: datetime,
        source_market_data_id: str,
        strategy_decision_id: UUID | None = None,
    ) -> "XAUUSDExecution":
        self = XAUUSDExecution.model_validate(self.model_dump())
        if self.position is not None:
            raise ExecutionError("open requires FLAT; no pyramiding or atomic reversal")
        quote = self._quote(quote, timestamp)
        direction = PositionDirection(direction)
        price = quote.price_for_side(direction.opening_side)
        position = PositionSnapshot(
            position_id=uuid5(self.simulation_id, "position"),
            canonical_symbol="XAUUSD",
            direction=direction,
            volume=volume,
            entry_price=price,
            opened_at=quote.timestamp,
        )
        fill = ExecutionFill(
            execution_id=uuid5(self.simulation_id, "OPEN"),
            position_id=position.position_id,
            intent="OPEN",
            direction=direction,
            action=direction.opening_side,
            executed_price=price,
            quote=quote,
            source_market_data_id=source_market_data_id,
            strategy_decision_id=strategy_decision_id,
        )
        return XAUUSDExecution(
            simulation_id=self.simulation_id, position=position, fills=(fill,)
        )

    def close(
        self,
        quote: MarketQuote,
        *,
        timestamp: datetime,
        source_market_data_id: str,
        strategy_decision_id: UUID | None = None,
    ) -> "XAUUSDExecution":
        self = XAUUSDExecution.model_validate(self.model_dump())
        if self.position is None or self.position.closed_at is not None:
            raise ExecutionError("close requires an open position")
        quote = self._quote(quote, timestamp)
        p = self.position
        if quote.timestamp < p.opened_at:
            raise ExecutionError("close cannot precede entry")
        price = quote.price_for_side(p.direction.closing_side)
        closed = PositionSnapshot.model_validate(
            p.model_dump() | {"closed_at": quote.timestamp, "exit_price": price}
        )
        fill = ExecutionFill(
            execution_id=uuid5(self.simulation_id, "CLOSE"),
            position_id=p.position_id,
            intent="CLOSE",
            direction=p.direction,
            action=p.direction.closing_side,
            executed_price=price,
            quote=quote,
            source_market_data_id=source_market_data_id,
            strategy_decision_id=strategy_decision_id,
        )
        return XAUUSDExecution(
            simulation_id=self.simulation_id, position=closed, fills=(*self.fills, fill)
        )
