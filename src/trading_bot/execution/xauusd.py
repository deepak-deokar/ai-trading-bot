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
from trading_bot.execution.protection import ProtectiveBarEvidence


class ExecutionError(ValueError):
    """Invalid lifecycle transition or unavailable executable observation."""


class ExecutionFill(DomainModel):
    execution_id: UUID
    position_id: UUID
    intent: Literal["OPEN", "CLOSE"]
    direction: PositionDirection
    action: Side
    executed_price: ExactPositive
    quote: MarketQuote | None = None
    protective_bar: ProtectiveBarEvidence | None = None
    source_market_data_id: str = Field(min_length=1)
    strategy_decision_id: UUID | None = None

    @model_validator(mode="after")
    def executable_side(self) -> Self:
        expected = (
            self.direction.opening_side
            if self.intent == "OPEN"
            else self.direction.closing_side
        )
        if (self.quote is None) == (self.protective_bar is None):
            raise ValueError(
                "fill requires exactly one quote or protective bar evidence"
            )
        price: Decimal | None
        if self.quote is not None:
            if self.quote.canonical_symbol != "XAUUSD":
                raise ValueError("execution requires canonical XAUUSD")
            price = self.quote.price_for_side(expected)
        else:
            assert self.protective_bar is not None
            evidence = self.protective_bar
            if (
                self.intent != "CLOSE"
                or evidence.instruction.position_id != self.position_id
                or evidence.instruction.direction != self.direction
                or evidence.source_market_data_id != self.source_market_data_id
            ):
                raise ValueError("protective bar evidence must match this close")
            price = evidence.fill_price
        if self.action != expected or self.executed_price != price:
            raise ValueError(
                "fill must match executable quote or explicit bar convention"
            )
        return self

    @property
    def timestamp(self) -> datetime:
        if self.quote is not None:
            return self.quote.timestamp
        assert self.protective_bar is not None
        return self.protective_bar.bar.closing_timestamp

    @property
    def canonical_symbol(self) -> str:
        return "XAUUSD"

    @property
    def bid(self) -> Decimal | None:
        return self.quote.bid if self.quote is not None else None

    @property
    def ask(self) -> Decimal | None:
        return self.quote.ask if self.quote is not None else None

    @property
    def spread(self) -> Decimal | None:
        return self.quote.spread if self.quote is not None else None


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
            if fill.protective_bar is not None:
                evidence = fill.protective_bar
                if (
                    not p.opened_at
                    <= evidence.instruction.created_at
                    <= evidence.bar.opening_timestamp
                ):
                    raise ValueError("protective instruction/bar cannot precede entry")
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

    def close_protective_bar(
        self, evidence: ProtectiveBarEvidence
    ) -> "XAUUSDExecution":
        """Close once using auditable modeled OHLC evidence, not a synthetic quote."""
        self = XAUUSDExecution.model_validate(self.model_dump())
        evidence = ProtectiveBarEvidence.model_validate(evidence.model_dump())
        p = self.position
        if p is None or p.closed_at is not None:
            raise ExecutionError("close requires an open position")
        price = evidence.fill_price
        if price is None:
            raise ExecutionError("bar has no protective trigger")
        closed = PositionSnapshot.model_validate(
            p.model_dump()
            | {"closed_at": evidence.bar.closing_timestamp, "exit_price": price}
        )
        fill = ExecutionFill(
            execution_id=uuid5(self.simulation_id, "CLOSE"),
            position_id=p.position_id,
            intent="CLOSE",
            direction=p.direction,
            action=p.direction.closing_side,
            executed_price=price,
            protective_bar=evidence,
            source_market_data_id=evidence.source_market_data_id,
        )
        return XAUUSDExecution(
            simulation_id=self.simulation_id, position=closed, fills=(*self.fills, fill)
        )
