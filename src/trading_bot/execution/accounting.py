"""Explicit linear USD accounting for closed research lifecycles only."""

import hashlib
import json
from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from trading_bot.domain.contracts import ContractSpecification
from trading_bot.domain.models import DomainModel
from trading_bot.execution.xauusd import XAUUSDExecution

ExactMoney = Annotated[Decimal, Field(strict=True, allow_inf_nan=False)]
NonnegativeMoney = Annotated[Decimal, Field(strict=True, ge=0, allow_inf_nan=False)]


class LinearUSDContract(DomainModel):
    """Operator assertion of units; not a verified broker specification."""

    specification: ContractSpecification
    price_unit: Literal["USD_PER_TROY_OUNCE"]
    contract_size_unit: Literal["TROY_OUNCES_PER_VOLUME_UNIT"]
    quote_currency: Literal["USD"]
    account_currency: Literal["USD"]

    @model_validator(mode="after")
    def no_ambiguous_tick_conversion(self) -> Self:
        if self.specification.tick_value is not None:
            raise ValueError("linear USD profile requires tick_value unset")
        return self

    @property
    def conversion_id(self) -> str:
        payload = self.model_dump(mode="json", exclude={"specification"})
        payload["specification_id"] = self.specification.specification_id
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class Commission(DomainModel):
    """Explicit total fee for both fills combined, applied exactly once."""

    currency: Literal["USD"]
    fixed_round_trip_usd: NonnegativeMoney


class RealizedUSDResult(DomainModel):
    lifecycle: XAUUSDExecution
    contract: LinearUSDContract
    contract_specification_id: str
    conversion_id: str
    commission_model: Commission
    raw_price_movement: ExactMoney
    gross_usd: ExactMoney
    commission_usd: NonnegativeMoney
    net_usd: ExactMoney
    slippage_usd: Annotated[Decimal, Field(strict=True, ge=0, le=0)] = Decimal("0")
    spread_treatment: Literal["EMBEDDED_IN_FILLS_NO_EXTRA_DEDUCTION"] = (
        "EMBEDDED_IN_FILLS_NO_EXTRA_DEDUCTION"
    )


def realize_usd(
    lifecycle: XAUUSDExecution,
    contract: LinearUSDContract,
    commission: Commission,
) -> RealizedUSDResult:
    """Convert supplied valid volume; no balance, risk sizing or FX conversion."""
    lifecycle = XAUUSDExecution.model_validate(lifecycle.model_dump())
    contract = LinearUSDContract.model_validate(contract.model_dump())
    commission = Commission.model_validate(commission.model_dump())
    position = lifecycle.position
    if position is None or position.closed_at is None or position.exit_price is None:
        raise ValueError("realized monetary accounting requires a CLOSED position")
    specification = contract.specification
    specification.validate_volume(position.volume)
    specification.validate_price(position.entry_price)
    specification.validate_price(position.exit_price)
    movement = lifecycle.price_movement
    assert movement is not None
    factors = (movement, specification.contract_size, position.volume)
    with localcontext() as context:
        context.prec = sum(len(v.as_tuple().digits) for v in factors) + 3
        gross = movement * specification.contract_size * position.volume
    fee = commission.fixed_round_trip_usd
    with localcontext() as context:
        context.prec = (
            max(gross.adjusted(), fee.adjusted())
            - min(int(gross.as_tuple().exponent), int(fee.as_tuple().exponent))
            + 3
        )
        net = gross - fee
    return RealizedUSDResult(
        lifecycle=lifecycle,
        contract=contract,
        contract_specification_id=specification.specification_id,
        conversion_id=contract.conversion_id,
        commission_model=commission,
        raw_price_movement=movement,
        gross_usd=gross,
        commission_usd=fee,
        net_usd=net,
    )
