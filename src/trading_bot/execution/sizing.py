"""Pure stop-risk sizing; no margin assessment or stop execution."""

from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from trading_bot.domain.contracts import ExactPositive
from trading_bot.domain.models import DomainModel
from trading_bot.execution.accounting import (
    Commission,
    LinearUSDContract,
    NonnegativeMoney,
)


class SizingRequest(DomainModel):
    account_equity: ExactPositive
    account_currency: Literal["USD"]
    risk_fraction: (
        Annotated[Decimal, Field(strict=True, gt=0, le=1, allow_inf_nan=False)] | None
    ) = None
    risk_amount: ExactPositive | None = None
    stop_distance: ExactPositive
    contract: LinearUSDContract
    commission: Commission
    stop_convention: Literal["EXECUTABLE_ENTRY_TO_EXECUTABLE_STOP_EXIT"] = (
        "EXECUTABLE_ENTRY_TO_EXECUTABLE_STOP_EXIT"
    )

    @model_validator(mode="after")
    def one_budget(self) -> Self:
        if (self.risk_fraction is None) == (self.risk_amount is None):
            raise ValueError("supply exactly one of risk_fraction or risk_amount")
        if self.risk_amount is not None and self.risk_amount > self.account_equity:
            raise ValueError("risk_amount must not exceed account equity")
        return self


class SizingStatus(StrEnum):
    SIZED = "SIZED"
    NO_VALID_VOLUME = "NO_VALID_VOLUME"


class SizingReason(StrEnum):
    RISK_BOUND = "RISK_BOUND"
    CONTRACT_MAXIMUM = "CONTRACT_MAXIMUM"
    COSTS_CONSUME_BUDGET = "COSTS_CONSUME_BUDGET"
    MINIMUM_EXCEEDS_BUDGET = "MINIMUM_EXCEEDS_BUDGET"


class SizingResult(DomainModel):
    request: SizingRequest
    contract_specification_id: str
    conversion_id: str
    risk_budget_usd: ExactPositive
    selected_volume: ExactPositive | None
    projected_gross_stop_loss: NonnegativeMoney | None
    projected_explicit_costs: NonnegativeMoney
    projected_net_stop_loss: NonnegativeMoney | None
    next_valid_volume: ExactPositive | None
    next_step_projected_loss: NonnegativeMoney | None
    status: SizingStatus
    reason: SizingReason
    calculation_version: Literal["linear-usd-stop-risk-v1"] = "linear-usd-stop-risk-v1"


def _decimal(value: Fraction) -> Decimal:
    """Exact finite conversion, independent of the caller's Decimal context.

    Only sums/products of finite Decimals enter here, never a volume quotient.
    """
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("non-terminating Decimal result")
    scale = max(twos, fives)
    coefficient = value.numerator * 2 ** (scale - twos) * 5 ** (scale - fives)
    digits = tuple(int(char) for char in str(abs(coefficient)))
    return Decimal((int(coefficient < 0), digits, -scale))


def size_position(request: SizingRequest) -> SizingResult:
    """Floor to the existing zero-origin volume grid; never round risk upward.

    Invalid/unsupported inputs raise Pydantic ValidationError. Valid requests
    whose minimum volume cannot fit return NO_VALID_VOLUME. Direction is not
    required: adverse executable-price distance has identical linear USD loss
    in both directions, with the same explicit fixed round-trip fee.
    """
    request = SizingRequest.model_validate(request.model_dump())
    specification = request.contract.specification
    budget = (
        Fraction(request.account_equity) * Fraction(request.risk_fraction)
        if request.risk_fraction is not None
        else Fraction(request.risk_amount)  # type: ignore[arg-type]
    )
    fee = Fraction(request.commission.fixed_round_trip_usd)
    loss_per_volume = Fraction(request.stop_distance) * Fraction(
        specification.contract_size
    )
    step = Fraction(specification.volume_step)
    minimum = Fraction(specification.minimum_volume)
    maximum = (
        Fraction(specification.maximum_volume)
        if specification.maximum_volume is not None
        else None
    )
    steps = max(0, (budget - fee) // (loss_per_volume * step))
    if maximum is not None:
        steps = min(steps, maximum // step)
    volume = steps * step
    selected: Decimal | None = None
    gross: Decimal | None = None
    total: Decimal | None = None
    next_volume: Decimal | None = None
    next_loss: Decimal | None = None
    if volume < minimum:
        status = SizingStatus.NO_VALID_VOLUME
        reason = (
            SizingReason.COSTS_CONSUME_BUDGET
            if fee >= budget
            else SizingReason.MINIMUM_EXCEEDS_BUDGET
        )
    else:
        selected = _decimal(volume)
        specification.validate_volume(selected)
        gross = _decimal(loss_per_volume * volume)
        total = _decimal(loss_per_volume * volume + fee)
        assert loss_per_volume * volume + fee <= budget
        status = SizingStatus.SIZED
        if maximum is None or volume + step <= maximum:
            next_volume = _decimal(volume + step)
            next_loss = _decimal(loss_per_volume * (volume + step) + fee)
            assert loss_per_volume * (volume + step) + fee > budget
            reason = SizingReason.RISK_BOUND
        else:
            reason = SizingReason.CONTRACT_MAXIMUM
    return SizingResult(
        request=request,
        contract_specification_id=specification.specification_id,
        conversion_id=request.contract.conversion_id,
        risk_budget_usd=_decimal(budget),
        selected_volume=selected,
        projected_gross_stop_loss=gross,
        projected_explicit_costs=request.commission.fixed_round_trip_usd,
        projected_net_stop_loss=total,
        next_valid_volume=next_volume,
        next_step_projected_loss=next_loss,
        status=status,
        reason=reason,
    )
