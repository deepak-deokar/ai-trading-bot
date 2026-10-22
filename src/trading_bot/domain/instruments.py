"""Canonical research identities, independent of provider symbols and bar storage."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from trading_bot.domain.market import Exchange, Segment
from trading_bot.domain.models import DomainModel, Symbol


class Currency(StrEnum):
    INR = "INR"
    USD = "USD"


class AssetClass(StrEnum):
    EQUITY = "EQUITY"
    SPOT_METAL = "SPOT_METAL"


class Instrument(DomainModel):
    """Canonical identity only; adapters will own broker/provider symbol mappings.

    SPOT_METAL describes the research underlying, not a broker contract or a
    guarantee that a future broker offers physical spot rather than a CFD.
    """

    symbol: Symbol
    asset_class: AssetClass
    base_asset: Symbol
    quote_currency: Currency
    exchange: Exchange | None = None
    segment: Segment | None = None

    @model_validator(mode="after")
    def consistent_identity(self) -> Self:
        if (self.exchange is None) != (self.segment is None):
            raise ValueError("exchange and segment must be supplied together")
        if self.asset_class == AssetClass.SPOT_METAL and self.exchange is not None:
            raise ValueError("spot metal cannot use the supported NSE CASH venue")
        if self.exchange == Exchange.NSE and (
            self.asset_class != AssetClass.EQUITY or self.quote_currency != Currency.INR
        ):
            raise ValueError("NSE CASH requires an INR equity")
        if self.symbol == "XAUUSD" and (
            self.asset_class != AssetClass.SPOT_METAL
            or self.base_asset != "XAU"
            or self.quote_currency != Currency.USD
        ):
            raise ValueError("XAUUSD requires SPOT_METAL, XAU and USD")
        return self
