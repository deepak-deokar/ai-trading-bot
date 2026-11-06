"""One explicit plan, causal bar-open entry and completed-bar monitoring."""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID, uuid5

from pydantic import Field, ValidationError, field_validator, model_validator

from trading_bot.domain.contracts import ContractValidationError, ExactPositive
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel
from trading_bot.domain.positions import PositionDirection, raw_price_movement
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote
from trading_bot.execution.accounting import (
    Commission,
    LinearUSDContract,
    RealizedUSDResult,
    realize_usd,
)
from trading_bot.execution.protection import ProtectiveInstruction, ProtectiveTrigger
from trading_bot.execution.protective_exits import ProtectiveEvaluation, evaluate_bar
from trading_bot.execution.sizing import (
    SizingRequest,
    SizingResult,
    SizingStatus,
    size_position,
)
from trading_bot.execution.xauusd import ExecutionFill, XAUUSDExecution


class TradePlan(DomainModel):
    plan_id: UUID
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    direction: PositionDirection
    created_at: datetime
    entry_timestamp: datetime
    stop_price: ExactPositive
    target_price: ExactPositive | None = None
    account_equity: ExactPositive
    account_currency: Literal["USD"]
    risk_fraction: (
        Annotated[Decimal, Field(strict=True, gt=0, le=1, allow_inf_nan=False)] | None
    ) = None
    risk_amount: ExactPositive | None = None
    contract: LinearUSDContract
    commission: Commission
    source_identity: str = Field(min_length=1)

    @field_validator("created_at", "entry_timestamp")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.entry_timestamp < self.created_at:
            raise ValueError("entry must not precede plan creation")
        if (self.risk_fraction is None) == (self.risk_amount is None):
            raise ValueError("supply exactly one risk fraction or amount")
        if self.risk_amount is not None and self.risk_amount > self.account_equity:
            raise ValueError("risk amount must not exceed equity")
        if not self.source_identity.strip():
            raise ValueError("source identity must be nonblank")
        return self


class SimulationBar(DomainModel):
    bar: QuoteBar
    source_market_data_id: str = Field(min_length=1)

    @field_validator("source_market_data_id")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("market-data identity must be nonblank")
        return value


class SimulationStatus(StrEnum):
    PENDING_AT_END = "PENDING_AT_END"
    OPEN_AT_END = "OPEN_AT_END"
    CLOSED_TARGET = "CLOSED_TARGET"
    CLOSED_STOP = "CLOSED_STOP"
    CLOSED_STOP_AMBIGUOUS = "CLOSED_STOP_AMBIGUOUS"
    NO_TRADE_RISK = "NO_TRADE_RISK"
    REJECTED_INVALID_PLAN = "REJECTED_INVALID_PLAN"


class SimulationEventType(StrEnum):
    PLAN_ACCEPTED = "PLAN_ACCEPTED"
    PLAN_REJECTED = "PLAN_REJECTED"
    VOLUME_SIZED = "VOLUME_SIZED"
    ENTRY_FILLED = "ENTRY_FILLED"
    PROTECTION_ATTACHED = "PROTECTION_ATTACHED"
    NO_EXIT = "NO_EXIT"
    STOP_TRIGGERED = "STOP_TRIGGERED"
    TARGET_TRIGGERED = "TARGET_TRIGGERED"
    POSITION_CLOSED = "POSITION_CLOSED"
    ACCOUNTING_COMPLETED = "ACCOUNTING_COMPLETED"
    RISK_BUDGET_BREACH = "RISK_BUDGET_BREACH"
    DATA_ENDED = "DATA_ENDED"


class SimulationReason(StrEnum):
    EXPLICIT_PLAN = "EXPLICIT_PLAN"
    INVALID_LEVELS_OR_PRICE_GRID = "INVALID_LEVELS_OR_PRICE_GRID"
    NO_VALID_VOLUME = "NO_VALID_VOLUME"
    NEXT_ELIGIBLE_BAR_OPEN = "NEXT_ELIGIBLE_BAR_OPEN"
    STATIC_PROTECTION = "STATIC_PROTECTION"
    NO_EXIT = "NO_EXIT"
    STOP = "STOP"
    TARGET = "TARGET"
    STOP_FIRST_CONSERVATIVE = "STOP_FIRST_CONSERVATIVE"
    RISK_BUDGET_EXCEEDED_BY_GAP = "RISK_BUDGET_EXCEEDED_BY_GAP"
    INPUT_EXHAUSTED = "INPUT_EXHAUSTED"
    NO_ELIGIBLE_COMPLETED_BAR = "NO_ELIGIBLE_COMPLETED_BAR"


class SimulatorEvent(DomainModel):
    sequence: int = Field(ge=0)
    event_id: UUID
    timestamp: datetime
    kind: SimulationEventType
    reason: SimulationReason
    source_market_data_id: str | None = None

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)


class SimulationResult(DomainModel):
    plan: TradePlan
    status: SimulationStatus
    lifecycle: XAUUSDExecution
    sizing: SizingResult | None
    entry_observation: SimulationBar | None
    protection: ProtectiveInstruction | None
    evaluations: tuple[ProtectiveEvaluation, ...]
    accounting: RealizedUSDResult | None
    risk_budget_breached: bool
    bars_processed: int = Field(ge=0)
    events: tuple[SimulatorEvent, ...]
    audit_reasons: tuple[SimulationReason, ...]
    simulator_version: Literal["xauusd-explicit-plan-v1"] = "xauusd-explicit-plan-v1"
    entry_convention: Literal["MODELED_BAR_OPEN_BID_ASK"] = "MODELED_BAR_OPEN_BID_ASK"

    @property
    def plan_id(self) -> UUID:
        return self.plan.plan_id

    @property
    def stop_price(self) -> Decimal:
        return self.plan.stop_price

    @property
    def target_price(self) -> Decimal | None:
        return self.plan.target_price

    @property
    def gross_pnl(self) -> Decimal | None:
        return self.accounting.gross_usd if self.accounting else None

    @property
    def costs(self) -> Decimal | None:
        return self.accounting.commission_usd if self.accounting else None

    @property
    def net_pnl(self) -> Decimal | None:
        return self.accounting.net_usd if self.accounting else None

    @property
    def position_id(self) -> UUID | None:
        return self.lifecycle.position.position_id if self.lifecycle.position else None

    @property
    def volume(self) -> Decimal | None:
        return self.lifecycle.position.volume if self.lifecycle.position else None

    @property
    def entry_fill(self) -> ExecutionFill | None:
        return self.lifecycle.fills[0] if self.lifecycle.fills else None

    @property
    def exit_fill(self) -> ExecutionFill | None:
        return self.lifecycle.fills[-1] if self.lifecycle.status == "CLOSED" else None

    @property
    def risk_budget(self) -> Decimal | None:
        return self.sizing.risk_budget_usd if self.sizing else None

    @property
    def projected_stop_risk(self) -> Decimal | None:
        return self.sizing.projected_net_stop_loss if self.sizing else None


class SimulationDataError(ValueError):
    """Invalid chronology/identity in the consumed prefix; never silently sorted."""


def simulate_trade(
    plan: TradePlan, observations: Iterable[SimulationBar], *, as_of: datetime
) -> SimulationResult:
    """Stream one plan; never consume observations after its terminal decision.

    Each eligible completed bar is replayed as opening then completion. Opening
    uses only bid_open/ask_open. Instructions are in place for that entire bar.
    Bars not complete by as_of cannot supply entry or protective observations.
    """
    plan = TradePlan.model_validate(plan.model_dump())
    as_of = utc(as_of)
    if as_of < plan.created_at:
        raise ValueError("as_of cannot precede plan creation")
    simulation_id = uuid5(plan.plan_id, "xauusd-explicit-plan-v1")
    lifecycle = XAUUSDExecution(simulation_id=simulation_id)
    sizing: SizingResult | None = None
    protection: ProtectiveInstruction | None = None
    entry_observation: SimulationBar | None = None
    accounting: RealizedUSDResult | None = None
    evaluations: list[ProtectiveEvaluation] = []
    events: list[SimulatorEvent] = []
    processed = 0
    breached = False

    def emit(
        timestamp: datetime,
        kind: SimulationEventType,
        reason: SimulationReason,
        source_id: str | None = None,
    ) -> None:
        if events and timestamp < events[-1].timestamp:
            raise SimulationDataError("event time cannot move backward")
        sequence = len(events)
        events.append(
            SimulatorEvent(
                sequence=sequence,
                event_id=uuid5(simulation_id, f"event:{sequence}:{kind.value}"),
                timestamp=timestamp,
                kind=kind,
                reason=reason,
                source_market_data_id=source_id,
            )
        )

    def finish(status: SimulationStatus, reason: SimulationReason) -> SimulationResult:
        reasons = [reason]
        if breached:
            reasons.append(SimulationReason.RISK_BUDGET_EXCEEDED_BY_GAP)
        return SimulationResult(
            plan=plan,
            status=status,
            lifecycle=lifecycle,
            sizing=sizing,
            entry_observation=entry_observation,
            protection=protection,
            evaluations=tuple(evaluations),
            accounting=accounting,
            risk_budget_breached=breached,
            bars_processed=processed,
            events=tuple(events),
            audit_reasons=tuple(reasons),
        )

    emit(
        plan.created_at,
        SimulationEventType.PLAN_ACCEPTED,
        SimulationReason.EXPLICIT_PLAN,
    )
    previous: datetime | None = None
    seen_ids: set[str] = set()
    for supplied in observations:
        observation = SimulationBar.model_validate(supplied.model_dump())
        bar, source_id = observation.bar, observation.source_market_data_id
        if previous is not None and bar.opening_timestamp <= previous:
            raise SimulationDataError(
                "bars must be strictly oldest to newest without duplicates"
            )
        if source_id in seen_ids:
            raise SimulationDataError("duplicate market-data identity")
        previous = bar.opening_timestamp
        seen_ids.add(source_id)
        if bar.closing_timestamp > as_of:
            break
        processed += 1
        if lifecycle.status == "FLAT":
            if bar.opening_timestamp < plan.entry_timestamp:
                continue
            # Only opening-side values are exposed to sizing and entry mechanics.
            opening = MarketQuote(
                canonical_symbol="XAUUSD",
                timestamp=bar.opening_timestamp,
                bid=bar.bid_open,
                ask=bar.ask_open,
            )
            entry_price = opening.price_for_side(plan.direction.opening_side)
            try:
                # Preflight prevents opening an unprotectable position. The final
                # attachment is emitted only after the central lifecycle opens.
                candidate = ProtectiveInstruction(
                    position_id=uuid5(simulation_id, "position"),
                    direction=plan.direction,
                    stop_price=plan.stop_price,
                    target_price=plan.target_price,
                    created_at=opening.timestamp,
                    creation_quote=opening,
                    source_identity=plan.source_identity,
                )
                specification = plan.contract.specification
                for price in (entry_price, plan.stop_price, plan.target_price):
                    if price is not None:
                        specification.validate_price(price)
            except (ValidationError, ContractValidationError):
                emit(
                    opening.timestamp,
                    SimulationEventType.PLAN_REJECTED,
                    SimulationReason.INVALID_LEVELS_OR_PRICE_GRID,
                    source_id,
                )
                return finish(
                    SimulationStatus.REJECTED_INVALID_PLAN,
                    SimulationReason.INVALID_LEVELS_OR_PRICE_GRID,
                )
            stop_distance = raw_price_movement(
                plan.direction, plan.stop_price, entry_price
            )
            sizing = size_position(
                SizingRequest(
                    account_equity=plan.account_equity,
                    account_currency=plan.account_currency,
                    risk_fraction=plan.risk_fraction,
                    risk_amount=plan.risk_amount,
                    stop_distance=stop_distance,
                    contract=plan.contract,
                    commission=plan.commission,
                )
            )
            if sizing.status == SizingStatus.NO_VALID_VOLUME:
                emit(
                    opening.timestamp,
                    SimulationEventType.PLAN_REJECTED,
                    SimulationReason.NO_VALID_VOLUME,
                    source_id,
                )
                return finish(
                    SimulationStatus.NO_TRADE_RISK, SimulationReason.NO_VALID_VOLUME
                )
            emit(
                opening.timestamp,
                SimulationEventType.VOLUME_SIZED,
                SimulationReason.NEXT_ELIGIBLE_BAR_OPEN,
                source_id,
            )
            assert sizing.selected_volume is not None
            lifecycle = lifecycle.open(
                plan.direction,
                sizing.selected_volume,
                opening,
                timestamp=opening.timestamp,
                source_market_data_id=source_id,
            )
            entry_observation = observation
            emit(
                opening.timestamp,
                SimulationEventType.ENTRY_FILLED,
                SimulationReason.NEXT_ELIGIBLE_BAR_OPEN,
                source_id,
            )
            protection = candidate
            emit(
                opening.timestamp,
                SimulationEventType.PROTECTION_ATTACHED,
                SimulationReason.STATIC_PROTECTION,
                source_id,
            )
        assert protection is not None
        evaluation = evaluate_bar(
            lifecycle,
            protection,
            bar,
            evaluated_at=bar.closing_timestamp,
            source_market_data_id=source_id,
        )
        evaluations.append(evaluation)
        lifecycle = evaluation.lifecycle
        if evaluation.trigger == ProtectiveTrigger.NO_EXIT:
            emit(
                bar.closing_timestamp,
                SimulationEventType.NO_EXIT,
                SimulationReason.NO_EXIT,
                source_id,
            )
            continue
        if evaluation.trigger == ProtectiveTrigger.TARGET_TRIGGERED:
            status = SimulationStatus.CLOSED_TARGET
            reason = SimulationReason.TARGET
            kind = SimulationEventType.TARGET_TRIGGERED
        else:
            status = (
                SimulationStatus.CLOSED_STOP_AMBIGUOUS
                if evaluation.intrabar_ambiguous
                else SimulationStatus.CLOSED_STOP
            )
            reason = (
                SimulationReason.STOP_FIRST_CONSERVATIVE
                if evaluation.intrabar_ambiguous
                else SimulationReason.STOP
            )
            kind = SimulationEventType.STOP_TRIGGERED
        emit(bar.closing_timestamp, kind, reason, source_id)
        emit(
            bar.closing_timestamp,
            SimulationEventType.POSITION_CLOSED,
            reason,
            source_id,
        )
        accounting = realize_usd(lifecycle, plan.contract, plan.commission)
        emit(
            bar.closing_timestamp,
            SimulationEventType.ACCOUNTING_COMPLETED,
            reason,
            source_id,
        )
        assert sizing is not None
        # copy_negate is exact even under a small ambient Decimal precision.
        breached = accounting.net_usd < sizing.risk_budget_usd.copy_negate()
        if breached:
            emit(
                bar.closing_timestamp,
                SimulationEventType.RISK_BUDGET_BREACH,
                SimulationReason.RISK_BUDGET_EXCEEDED_BY_GAP,
                source_id,
            )
        return finish(status, reason)
    status = (
        SimulationStatus.OPEN_AT_END
        if lifecycle.status == "OPEN"
        else SimulationStatus.PENDING_AT_END
    )
    reason = (
        SimulationReason.INPUT_EXHAUSTED
        if lifecycle.status == "OPEN"
        else SimulationReason.NO_ELIGIBLE_COMPLETED_BAR
    )
    emit(as_of, SimulationEventType.DATA_ENDED, reason)
    return finish(status, reason)
