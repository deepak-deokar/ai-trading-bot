"""Broker-neutral quantity metadata and pure validation, without sizing/execution."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel

ExactPositive = Annotated[Decimal, Field(strict=True, gt=0, allow_inf_nan=False)]


class SpecificationSource(StrEnum):
    MT5_TERMINAL = "MT5_TERMINAL"
    BROKER_DOCUMENTATION = "BROKER_DOCUMENTATION"
    TEST_FIXTURE = "TEST_FIXTURE"
    MANUAL_RESEARCH = "MANUAL_RESEARCH"


class ContractValidationCode(StrEnum):
    INVALID_DECIMAL = "INVALID_DECIMAL"
    BELOW_MINIMUM = "BELOW_MINIMUM"
    ABOVE_MAXIMUM = "ABOVE_MAXIMUM"
    VOLUME_STEP = "VOLUME_STEP"
    PRICE_TICK = "PRICE_TICK"


class ContractValidationError(ValueError):
    def __init__(self, code: ContractValidationCode) -> None:
        self.code = code
        super().__init__(code.value)


def _positive(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ContractValidationError(ContractValidationCode.INVALID_DECIMAL)


def _aligned(value: Decimal, increment: Decimal) -> bool:
    # Integer ratios avoid Decimal context rounding, even at very high precision.
    numerator, denominator = value.as_integer_ratio()
    step_numerator, step_denominator = increment.as_integer_ratio()
    return (numerator * step_denominator) % (denominator * step_numerator) == 0


def _decimal_identity(value: Decimal) -> str:
    numerator, denominator = value.as_integer_ratio()
    return f"{numerator}/{denominator}"


class ContractSpecification(DomainModel):
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    broker_symbol: str | None = Field(default=None, min_length=1, max_length=128)
    contract_size: ExactPositive
    minimum_volume: ExactPositive
    maximum_volume: ExactPositive | None = None
    volume_step: ExactPositive
    tick_size: ExactPositive
    tick_value: ExactPositive | None = None
    price_digits: int | None = Field(default=None, ge=0, strict=True)
    minimum_stop_distance: ExactPositive | None = None
    specification_source: SpecificationSource
    observed_at: datetime | None = None
    schema_version: Literal[1] = 1

    @field_validator("broker_symbol")
    @classmethod
    def nonblank_symbol(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError(
                "broker symbol must be nonblank without surrounding spaces"
            )
        return value

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def consistent_bounds(self) -> Self:
        if (
            self.maximum_volume is not None
            and self.maximum_volume < self.minimum_volume
        ):
            raise ValueError("maximum_volume must be >= minimum_volume")
        if not _aligned(self.minimum_volume, self.volume_step):
            raise ValueError("minimum_volume must lie on the zero-origin volume grid")
        return self

    def validate_volume(self, volume: Decimal) -> None:
        """Raise a typed error on invalid volume; never modify or round the input."""
        _positive(volume)
        if volume < self.minimum_volume:
            raise ContractValidationError(ContractValidationCode.BELOW_MINIMUM)
        if self.maximum_volume is not None and volume > self.maximum_volume:
            raise ContractValidationError(ContractValidationCode.ABOVE_MAXIMUM)
        if not _aligned(volume, self.volume_step):
            raise ContractValidationError(ContractValidationCode.VOLUME_STEP)

    def validate_price(self, price: Decimal) -> None:
        """Check positive price on a zero-origin tick grid; not an order check."""
        _positive(price)
        if not _aligned(price, self.tick_size):
            raise ContractValidationError(ContractValidationCode.PRICE_TICK)

    @property
    def specification_id(self) -> str:
        """SHA-256 of all fields, including source, observation and schema version.

        Equal Decimal values with different trailing zeroes have the same identity.
        """
        payload = self.model_dump(mode="json")
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, Decimal):
                payload[name] = _decimal_identity(value)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()
