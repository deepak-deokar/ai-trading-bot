"""Causal fixed 12-bar structure and entry-time 2R levels; no execution."""

import hashlib
import json
from collections import deque
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.domain.contracts import ExactPositive
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side
from trading_bot.domain.positions import PositionDirection, raw_price_movement
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote
from trading_bot.execution.accounting import Commission, LinearUSDContract
from trading_bot.execution.protection import ProtectiveInstruction
from trading_bot.execution.simulator import TradePlan
from trading_bot.execution.sizing import SizingRequest
from trading_bot.strategies.xauusd import XAUUSDSignalDecision


class StructureBar(DomainModel):
    dataset: QuoteDataset
    bar: QuoteBar
    discontinuity_before: bool = False

    @property
    def source_identity(self) -> str:
        return f"{self.dataset.dataset_key}:{self.bar.opening_timestamp.isoformat()}"


class PlanningStatus(StrEnum):
    PLANNED = "PLANNED"
    NO_TRADE_INSUFFICIENT_STRUCTURE = "NO_TRADE_INSUFFICIENT_STRUCTURE"
    NO_TRADE_INVALID_STOP = "NO_TRADE_INVALID_STOP"
    NO_TRADE_INVALID_TARGET = "NO_TRADE_INVALID_TARGET"
    NO_TRADE_CONTRACT_ALIGNMENT = "NO_TRADE_CONTRACT_ALIGNMENT"
    NO_TRADE_SIGNAL = "NO_TRADE_SIGNAL"


class StructurePlan(DomainModel):
    decision: XAUUSDSignalDecision
    decision_key: str
    direction: PositionDirection | None
    source_bars: tuple[StructureBar, ...]
    structural_stop: ExactPositive | None
    status: PlanningStatus
    reason: str
    lookback: Literal[12] = 12
    target_multiple: Annotated[Decimal, Field(strict=True, ge=2, le=2)] = Decimal("2")
    planner_version: Literal["xauusd-structure-12-2r-v1"] = "xauusd-structure-12-2r-v1"
    target_derivation: Literal["ENTRY_PLUS_OR_MINUS_2R_ON_ALIGNED_STOP"] = (
        "ENTRY_PLUS_OR_MINUS_2R_ON_ALIGNED_STOP"
    )


class FinalizedLevels(DomainModel):
    structure: StructurePlan
    entry_quote: MarketQuote
    source_market_data_id: str = Field(min_length=1)
    status: PlanningStatus
    reason: str
    aligned_stop: ExactPositive | None = None
    raw_target: ExactPositive | None = None
    target: ExactPositive | None = None
    sizing_request: SizingRequest | None = None
    trade_plan: TradePlan | None = None


def plan_structure(
    decision: XAUUSDSignalDecision,
    observations: Iterable[StructureBar],
    *,
    as_of: datetime,
) -> StructurePlan:
    decision = XAUUSDSignalDecision.model_validate(decision.model_dump())
    if utc(as_of) < decision.available_at:
        raise ValueError("signal is not available at cutoff")
    if decision.available_at != decision.opening_timestamp + timedelta(minutes=5):
        raise ValueError("signal must identify a completed five-minute bar")
    key = hashlib.sha256(
        json.dumps(
            decision.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    direction = (
        None
        if decision.side is None
        else (
            PositionDirection.LONG
            if decision.side == Side.BUY
            else PositionDirection.SHORT
        )
    )
    window: deque[StructureBar] = deque(maxlen=12)

    def result(
        status: PlanningStatus, reason: str, stop: Decimal | None = None
    ) -> StructurePlan:
        return StructurePlan(
            decision=decision,
            decision_key=key,
            direction=direction,
            source_bars=tuple(window),
            structural_stop=stop,
            status=status,
            reason=reason,
        )

    if direction is None:
        return result(PlanningStatus.NO_TRADE_SIGNAL, "DECISION_HAS_NO_SIDE")
    previous: StructureBar | None = None
    found = False
    for supplied in observations:
        # Only time is inspected to stop at the causal boundary; no future prices.
        if supplied.bar.opening_timestamp > decision.opening_timestamp:
            break
        item = StructureBar.model_validate(supplied.model_dump())
        b, dataset = item.bar, item.dataset
        if (
            not dataset.start
            <= b.opening_timestamp
            < b.closing_timestamp
            <= dataset.end
        ):
            raise ValueError("source bar is outside its research-day dataset")
        if previous is not None:
            elapsed = b.opening_timestamp - previous.bar.opening_timestamp
            if elapsed <= timedelta(0):
                raise ValueError(
                    "structure observations must be strictly chronological"
                )
            if (
                elapsed != timedelta(minutes=5)
                or dataset.dataset_key != previous.dataset.dataset_key
                or dataset.selected_source_date != previous.dataset.selected_source_date
            ):
                window.clear()
        if item.discontinuity_before:
            window.clear()
        window.append(item)
        previous = item
        if b.opening_timestamp == decision.opening_timestamp:
            found = True
            break
    if (
        not found
        or len(window) != 12
        or any(
            item.dataset.dataset_key != decision.source_dataset_key for item in window
        )
    ):
        return result(
            PlanningStatus.NO_TRADE_INSUFFICIENT_STRUCTURE,
            "REQUIRE_12_CONTINUOUS_SAME_DAY_DATASET_BARS_ENDING_AT_SIGNAL",
        )
    stop = (
        min(item.bar.bid_low for item in window)
        if direction == PositionDirection.LONG
        else max(item.bar.ask_high for item in window)
    )
    return result(PlanningStatus.PLANNED, "STRUCTURE_AT_SIGNAL_ONLY", stop)


def _align(value: Decimal, tick: Decimal, *, upward: bool) -> Decimal:
    ratio = Fraction(value) / Fraction(tick)
    count = (
        -(-ratio.numerator // ratio.denominator)
        if upward
        else ratio.numerator // ratio.denominator
    )
    with localcontext() as context:
        context.prec = len(tick.as_tuple().digits) + len(str(abs(count))) + 3
        return Decimal(count) * tick


def finalize_levels(
    structure: StructurePlan,
    entry_quote: MarketQuote,
    *,
    source_market_data_id: str,
    contract: LinearUSDContract,
    commission: Commission,
    account_equity: Decimal,
    risk_fraction: Decimal | None = None,
    risk_amount: Decimal | None = None,
) -> FinalizedLevels:
    """Finalize at an observed executable entry, without sizing or opening a trade.

    The returned TradePlan is bound to this quote/time. Future integration must
    finalize at the actual entry event, not replay it at an unrelated later open.
    """
    structure = StructurePlan.model_validate(structure.model_dump())
    # Recompute signal-time evidence; reject forged/stale stops or result metadata.
    verified = plan_structure(
        structure.decision, structure.source_bars, as_of=structure.decision.available_at
    )
    if verified != structure:
        raise ValueError("structure result does not match retained causal evidence")
    quote = MarketQuote.model_validate(entry_quote.model_dump())
    contract = LinearUSDContract.model_validate(contract.model_dump())
    commission = Commission.model_validate(commission.model_dump())
    if (
        quote.canonical_symbol != "XAUUSD"
        or quote.timestamp < structure.decision.available_at
        or not source_market_data_id.strip()
    ):
        raise ValueError(
            "identified XAUUSD entry must be at or after signal completion"
        )

    def rejected(status: PlanningStatus, reason: str) -> FinalizedLevels:
        return FinalizedLevels(
            structure=structure,
            entry_quote=quote,
            source_market_data_id=source_market_data_id,
            status=status,
            reason=reason,
        )

    if structure.status != PlanningStatus.PLANNED:
        return rejected(structure.status, structure.reason)
    direction, raw_stop = structure.direction, structure.structural_stop
    assert direction is not None and raw_stop is not None
    entry = quote.price_for_side(direction.opening_side)
    exit_price = quote.price_for_side(direction.closing_side)
    long = direction == PositionDirection.LONG
    # Check the original structural thesis before alignment can move it outward.
    if raw_stop >= exit_price if long else raw_stop <= exit_price:
        return rejected(
            PlanningStatus.NO_TRADE_INVALID_STOP,
            "ENTRY_GAP_INVALIDATES_ORIGINAL_EXECUTABLE_STOP",
        )
    specification = contract.specification
    # MarketQuote validates the observed entry; only generated levels use the grid.
    stop = _align(raw_stop, specification.tick_size, upward=not long)
    if stop <= 0:
        return rejected(
            PlanningStatus.NO_TRADE_CONTRACT_ALIGNMENT, "ALIGNED_STOP_NOT_POSITIVE"
        )
    distance = raw_price_movement(direction, stop, entry)
    with localcontext() as context:
        context.prec = (
            max(entry.adjusted(), distance.adjusted())
            - min(int(entry.as_tuple().exponent), int(distance.as_tuple().exponent))
            + 10
        )
        raw_target = (
            entry + Decimal(2) * distance if long else entry - Decimal(2) * distance
        )
    if raw_target <= 0:
        return rejected(
            PlanningStatus.NO_TRADE_INVALID_TARGET, "DERIVED_TARGET_NOT_POSITIVE"
        )
    target = _align(raw_target, specification.tick_size, upward=not long)
    if target <= 0:
        return rejected(
            PlanningStatus.NO_TRADE_CONTRACT_ALIGNMENT, "ALIGNED_TARGET_NOT_POSITIVE"
        )
    specification.validate_price(stop)
    specification.validate_price(target)
    request = SizingRequest(
        account_equity=account_equity,
        account_currency="USD",
        risk_fraction=risk_fraction,
        risk_amount=risk_amount,
        stop_distance=distance,
        contract=contract,
        commission=commission,
    )
    plan_id = uuid5(
        NAMESPACE_URL,
        f"{structure.decision_key}:{structure.planner_version}:{source_market_data_id}:{quote.timestamp.isoformat()}",
    )
    # Reuse the exact G2C4B4 relationship validation; no competing exit rule.
    ProtectiveInstruction(
        position_id=plan_id,
        direction=direction,
        stop_price=stop,
        target_price=target,
        created_at=quote.timestamp,
        creation_quote=quote,
        source_identity=structure.decision_key,
    )
    plan = TradePlan(
        plan_id=plan_id,
        direction=direction,
        created_at=quote.timestamp,
        entry_timestamp=quote.timestamp,
        stop_price=stop,
        target_price=target,
        account_equity=request.account_equity,
        account_currency="USD",
        risk_fraction=request.risk_fraction,
        risk_amount=request.risk_amount,
        contract=contract,
        commission=commission,
        source_identity=structure.decision_key,
    )
    return FinalizedLevels(
        structure=structure,
        entry_quote=quote,
        source_market_data_id=source_market_data_id,
        status=PlanningStatus.PLANNED,
        reason="FINALIZED_AT_EXECUTABLE_ENTRY_NO_EXECUTION",
        aligned_stop=stop,
        raw_target=raw_target,
        target=target,
        sizing_request=request,
        trade_plan=plan,
    )
