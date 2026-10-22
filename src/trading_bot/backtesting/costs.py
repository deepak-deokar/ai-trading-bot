"""Versioned reference costs, incremental per-order charging across partial fills."""

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal, Protocol

import yaml
from pydantic import Field

from trading_bot.backtesting.orders import Side
from trading_bot.domain.models import DomainModel

ZERO = Decimal(0)


class CostBreakdown(DomainModel):
    brokerage: Decimal = ZERO
    stt: Decimal = ZERO
    stamp_duty: Decimal = ZERO
    exchange: Decimal = ZERO
    sebi: Decimal = ZERO
    ipft: Decimal = ZERO
    gst: Decimal = ZERO
    other: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return sum((getattr(self, k) for k in type(self).model_fields), ZERO)

    def difference(self, previous: "CostBreakdown") -> "CostBreakdown":
        return CostBreakdown(
            **{
                k: getattr(self, k) - getattr(previous, k)
                for k in type(self).model_fields
            }
        )

    def plus(self, other: "CostBreakdown") -> "CostBreakdown":
        return CostBreakdown(
            **{k: getattr(self, k) + getattr(other, k) for k in type(self).model_fields}
        )


class CostProfile(DomainModel):
    name: str
    version: str
    market: Literal["NSE:CASH:INTRADAY"]
    sources: tuple[str, ...]
    reviewed_on: str
    effective_from: str | None
    verification: str
    rounding: Literal["PAISA_HALF_UP_PER_ORDER_COMPONENT"]
    rounding_verified: Literal[False]
    warnings: tuple[str, ...]
    brokerage_rate: Decimal = Field(ge=0, le=1)
    brokerage_cap: Decimal = Field(ge=0)
    brokerage_minimum: Decimal = Field(ge=0)
    minimum_turnover_cap: Decimal = Field(ge=0, le=1)
    stt_sell: Decimal = Field(ge=0, le=1)
    stamp_buy: Decimal = Field(ge=0, le=1)
    exchange_rate: Decimal = Field(ge=0, le=1)
    sebi_rate: Decimal = Field(ge=0, le=1)
    ipft_rate: Decimal = Field(ge=0, le=1)
    gst_rate: Decimal = Field(ge=0, le=1)
    gst_components: tuple[
        Literal["brokerage", "exchange", "sebi", "ipft", "other"], ...
    ]
    other_rate: Decimal = Field(ge=0, le=1)
    square_off_charge: Decimal = Field(ge=0)


class TradingCostModel(Protocol):
    def manifest(self) -> dict[str, object]: ...
    def cumulative(
        self, side: Side, turnover: Decimal, *, forced: bool = False
    ) -> CostBreakdown: ...


class ZeroCostModel:
    def manifest(self) -> dict[str, object]:
        return {"name": "zero", "version": "1", "warnings": []}

    def cumulative(
        self, side: Side, turnover: Decimal, *, forced: bool = False
    ) -> CostBreakdown:
        return CostBreakdown()


class ReferenceCostModel:
    def __init__(self, profile: CostProfile) -> None:
        self.profile = CostProfile.model_validate(profile.model_dump())

    @classmethod
    def load(cls, path: Path) -> "ReferenceCostModel":
        return cls(CostProfile.model_validate(yaml.safe_load(path.read_text())))

    def manifest(self) -> dict[str, object]:
        return self.profile.model_dump(mode="json")

    def cumulative(
        self, side: Side, turnover: Decimal, *, forced: bool = False
    ) -> CostBreakdown:
        if turnover < 0 or not turnover.is_finite():
            raise ValueError("invalid executed turnover")
        if turnover == 0:
            return CostBreakdown()
        p = self.profile

        def money(value: Decimal) -> Decimal:
            return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        brokerage = max(
            min(p.brokerage_cap, turnover * p.brokerage_rate),
            min(p.brokerage_minimum, turnover * p.minimum_turnover_cap),
        )
        values = dict(
            brokerage=money(brokerage),
            stt=money(turnover * p.stt_sell) if side == Side.SELL else ZERO,
            stamp_duty=money(turnover * p.stamp_buy) if side == Side.BUY else ZERO,
            exchange=money(turnover * p.exchange_rate),
            sebi=money(turnover * p.sebi_rate),
            ipft=money(turnover * p.ipft_rate),
            other=money(
                turnover * p.other_rate + (p.square_off_charge if forced else ZERO)
            ),
        )
        values["gst"] = money(
            sum((values[k] for k in p.gst_components), ZERO) * p.gst_rate
        )
        return CostBreakdown(**values)
