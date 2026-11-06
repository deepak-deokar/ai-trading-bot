"""Pure protective evaluation of an already-sized XAUUSD lifecycle."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import field_validator

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote
from trading_bot.execution.protection import (
    ProtectiveBarEvidence,
    ProtectiveInstruction,
    ProtectiveTrigger,
)
from trading_bot.execution.xauusd import ExecutionError, XAUUSDExecution


class ProtectiveEvaluation(DomainModel):
    instruction: ProtectiveInstruction
    lifecycle: XAUUSDExecution
    observation: MarketQuote | ProtectiveBarEvidence
    evaluated_at: datetime
    trigger: ProtectiveTrigger
    source_market_data_id: str

    @field_validator("evaluated_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @property
    def position_id(self) -> UUID:
        return self.instruction.position_id

    @property
    def execution_side(self) -> Side:
        return self.instruction.direction.closing_side

    @property
    def trigger_market_side(self) -> Literal["BID", "ASK"]:
        return self.instruction.market_side

    @property
    def intrabar_ambiguous(self) -> bool:
        return self.trigger == ProtectiveTrigger.STOP_TRIGGERED_AMBIGUOUS

    @property
    def ambiguity_reason(self) -> str | None:
        return (
            "BOTH_LEVELS_TOUCHED_TICK_ORDER_UNKNOWN"
            if self.intrabar_ambiguous
            else None
        )

    @property
    def fill_id(self) -> UUID | None:
        if self.trigger in (
            ProtectiveTrigger.NO_EXIT,
            ProtectiveTrigger.ALREADY_CLOSED,
        ):
            return None
        return self.lifecycle.fills[-1].execution_id

    @property
    def fill_price(self) -> Decimal | None:
        return (
            self.lifecycle.fills[-1].executed_price
            if self.fill_id is not None
            else None
        )


def _inputs(
    lifecycle: XAUUSDExecution, instruction: ProtectiveInstruction
) -> tuple[XAUUSDExecution, ProtectiveInstruction]:
    lifecycle = XAUUSDExecution.model_validate(lifecycle.model_dump())
    instruction = ProtectiveInstruction.model_validate(instruction.model_dump())
    p = lifecycle.position
    if p is None:
        raise ExecutionError("protective evaluation requires an existing position")
    if p.position_id != instruction.position_id or p.direction != instruction.direction:
        raise ExecutionError("instruction must match position identity and direction")
    if instruction.created_at < p.opened_at:
        raise ExecutionError("instruction cannot precede entry")
    return lifecycle, instruction


def evaluate_quote(
    lifecycle: XAUUSDExecution,
    instruction: ProtectiveInstruction,
    quote: MarketQuote,
    *,
    evaluated_at: datetime,
    source_market_data_id: str,
) -> ProtectiveEvaluation:
    lifecycle, instruction = _inputs(lifecycle, instruction)
    quote = MarketQuote.model_validate(quote.model_dump())
    evaluated_at = utc(evaluated_at)
    if (
        quote.canonical_symbol != "XAUUSD"
        or quote.timestamp != evaluated_at
        or quote.timestamp < instruction.created_at
        or not source_market_data_id.strip()
    ):
        raise ExecutionError(
            "requires identified XAUUSD quote at evaluation time after creation"
        )
    trigger = (
        ProtectiveTrigger.ALREADY_CLOSED
        if lifecycle.status == "CLOSED"
        else instruction.quote_trigger(quote)
    )
    if trigger not in (ProtectiveTrigger.NO_EXIT, ProtectiveTrigger.ALREADY_CLOSED):
        lifecycle = lifecycle.close(
            quote, timestamp=evaluated_at, source_market_data_id=source_market_data_id
        )
    return ProtectiveEvaluation(
        instruction=instruction,
        lifecycle=lifecycle,
        observation=quote,
        evaluated_at=evaluated_at,
        trigger=trigger,
        source_market_data_id=source_market_data_id,
    )


def evaluate_bar(
    lifecycle: XAUUSDExecution,
    instruction: ProtectiveInstruction,
    bar: QuoteBar,
    *,
    evaluated_at: datetime,
    source_market_data_id: str,
) -> ProtectiveEvaluation:
    lifecycle, instruction = _inputs(lifecycle, instruction)
    evidence = ProtectiveBarEvidence.model_validate(
        dict(
            instruction=instruction.model_dump(),
            bar=bar.model_dump(),
            evaluated_at=evaluated_at,
            source_market_data_id=source_market_data_id,
        )
    )
    trigger = (
        ProtectiveTrigger.ALREADY_CLOSED
        if lifecycle.status == "CLOSED"
        else evidence.trigger
    )
    if trigger not in (ProtectiveTrigger.NO_EXIT, ProtectiveTrigger.ALREADY_CLOSED):
        lifecycle = lifecycle.close_protective_bar(evidence)
    return ProtectiveEvaluation(
        instruction=instruction,
        lifecycle=lifecycle,
        observation=evidence,
        evaluated_at=evidence.evaluated_at,
        trigger=trigger,
        source_market_data_id=source_market_data_id,
    )
